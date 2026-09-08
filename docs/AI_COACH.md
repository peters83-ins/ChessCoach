# AI Coach Architecture

The coach follows one directional pipeline:

`saved game → Stockfish → verified evidence → feedback → weaknesses → practice → lessons`

Stockfish supplies scores and principal variations. python-chess validates every
position, move, evidence input, AI continuation, and practice attempt. Feedback
providers may explain these facts but cannot create chess truth.

## Analysis

`GameAnalysisService` keeps one engine open per job. It first scans every ply with
the quick limit, analyzing the best move and the played move from the same root.
Positions near grading boundaries, losing at least five winning-chance points, or
containing mate scores receive a second deep pass. Cancellation is checked between
queries, each completed result enters the persistent cache, and progress identifies
quick, deep, and feedback stages.

Scores are normalized to White's perspective and mapped to a bounded win estimate.
Loss is measured for the moving side. Grades use these thresholds:

| Winning-chance loss | Grade |
| --- | --- |
| best engine move or ≤0.5 points | Best |
| ≤2 points | Excellent |
| <5 points | Good |
| 5–10 points | Inaccuracy |
| 10–20 points | Mistake |
| ≥20 points or damaging mate transition | Blunder |

Accuracy is `max(0, 100 - 1.5 × loss points)`. Game accuracy is a weighted average
of the learner's moves, emphasizing balanced and critical positions. It is a Chess
Coach metric and is not presented as another service's proprietary accuracy.

## Feedback and privacy

The local provider always produces feedback from deterministic evidence. If OpenAI
is configured, only critical learner positions are batched in groups of four. Each
request contains a FEN, played/best moves, PVs, classification, loss, and evidence
IDs. It does not contain the full PGN. Structured responses must reference permitted
evidence and contain a legal continuation or they are discarded in favor of the
local result. Cache identity includes context, provider model, and prompt version.

## Learning loop

Weakness events use stable tags such as opening principles, development, calculation,
material, hanging pieces, forks, knight tactics, and endgames. Severity and confidence
build a default local learner profile; successful practice can later add `mastered`
events to reduce a score.

Mistakes generate deduplicated interactive positions from the pre-move FEN and an
engine-verified solution. Correct and failed attempts adjust review intervals through
the 1, 3, 7, 14, and 30-day schedule. Lessons combine reviewed local concept text with
examples and exercises from the learner's stored games.

## Persistence and extension

`CoachRepository` applies additive SQLite migrations and separates analysis runs,
cached move analysis, feedback, profiles, weakness events, practice attempts, lessons,
and lesson progress. Analysis can therefore be regenerated without feedback, and
feedback can be regenerated without rerunning Stockfish.

New engines and text services implement the existing analysis and feedback protocols.
New motifs must produce deterministic evidence with stable IDs and tests. New theory
content should be reviewed, attributed, and stored separately from generated wording.
