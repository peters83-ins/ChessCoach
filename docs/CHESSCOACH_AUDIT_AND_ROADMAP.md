# Chess Coach Engine, GUI, and Workflow Audit

Updated: 2026-09-09

This is the canonical audit and development roadmap. It consolidates the former
first-pass backlog, UX audit, and roadmap status documents. Completed work remains
regression scope; the staged backlog below is the active queue.

## Baseline

- Python 3.12+, python-chess, Stockfish, PySide6, SQLite, and optional OpenAI feedback.
- Stockfish and python-chess are authoritative for legality, evaluation, and tactics.
- OpenAI is an optional explanation layer and must only receive verified facts.
- Baseline validation: 166 passed, 8 skipped; coverage approximately 88%.
- Real-Stockfish tests are opt-in through `CHESSCOACH_TEST_STOCKFISH`.
- Completed: P0/P1, P2 Stages A–F, modern GUI pass, adaptive practice, course catalog,
  review insights, opening/phase transfer metrics, supporting-position links, themed
  practice links, and related-course links.

## Audit findings

| ID | Severity | Area | Reproduction | Expected | Current finding | Regression / acceptance |
| --- | --- | --- | --- | --- | --- | --- |
| AUD-001 | high | Navigation | Open several toolbar destinations quickly | One stable workspace should switch instantly | Remaining destinations are dialog-based and can block or stack workflows | Scripted rapid switching leaves one active destination with no uncaught exception |
| AUD-002 | medium | Coverage | Inspect coverage after the full suite | Core UI and workers should have meaningful interaction coverage | Course UI, Insights UI, engine workers, and MainWindow paths remain lower coverage | Add focused Qt tests for controls, failure paths, and stale results |
| AUD-003 | high | Engine | Run without a configured executable | The app should explain the state and recover | Real Stockfish validation is skipped unless explicitly configured | Fake-engine tests cover deterministic behavior; opt-in real matrix passes at 800/1000/1200 and full strength |
| AUD-004 | high | Engine worker | Replace the board while a search is running | A stale result must never alter the new position | Generation/FEN protections exist but require stress regression coverage | Repeated new-game, undo, load, close, and delayed-result sequences remain safe |
| AUD-005 | medium | Learning workflow | Open Learn with an enrolled course | Continue should open the exact next module/decision | Course links and resume paths need a shared destination model | One action reaches the saved module or first due decision |
| AUD-006 | medium | Accessibility | Navigate course and board controls by keyboard/screen reader | Every control has a name, focus state, and predictable order | Labels exist for major course/board controls; native verification remains | Scripted focus assertions plus documented Windows keyboard/screen-reader pass |
| AUD-007 | medium | Insights | Inspect metrics with small datasets | Claims should explain evidence and sample limits | Local metrics have safeguards and links, but richer chart interaction remains | Every displayed metric exposes its source and suppresses insufficient samples |
| AUD-008 | low | Visual | Resize board/details and inspect empty states | Layout should remain readable and responsive | Modern theme is in place; chart and shared-content polish remain | Board stays square, focus is visible, and empty states offer a next action |

## Stress-test matrix

The automated audit uses offscreen Qt and deterministic fake engines. Each sequence
must finish without an uncaught exception and leave the application in a valid state.

- Play: color/difficulty selection, legal highlights, repeated New Game/Undo/Claim Draw,
  bot delay, Black opening move, engine retry, and stale result replacement.
- Persistence: save twice, load several games, delete/export, corrupt/old database,
  close during analysis, reopen, and verify moves/FEN/timestamps remain intact.
- Review: long histories, slider and keyboard navigation, graph/bar clicks, attacks,
  key moments, show line, retry rollback, cancellation, and resume.
- Learning: Learn, Courses, Lessons, Practice, Insights, Settings, diagnostics, empty
  states, filters, course resume, failed-attempt filters, and repeated destination opens.
- Engine failures: missing executable, malformed output, illegal move, crash, timeout,
  cancellation, invalid FEN, terminal board, promotion, mate, and repetition.
- Accessibility: tab order, keyboard activation, accessible names/descriptions, disabled
  explanations, focus visibility, contrast, and status indicators that do not rely on
  color alone.

## Chess.com workflow comparison

Chess.com Game Review emphasizes highlights, accuracy, key moments, explanations, retry,
and deeper analysis. Its Lessons product combines a guided path with a searchable lesson
library and short interactive challenges. Practice supports openings, master games,
drills, and custom positions with selected color and engine strength. Spaced repetition
tracks individual moves at different review levels. Insights compares periods, openings,
phases, tactics, move quality, and supporting positions.

Chess Coach follows those interaction patterns while keeping its own scoring, wording,
visual identity, reviewed offline content, and local-first data model.

- [Game Review](https://support.chess.com/en/articles/8584089-how-does-game-review-work)
- [Lessons](https://support.chess.com/en/articles/8609703-how-do-lessons-work-on-chess-com)
- [Practice](https://support.chess.com/en/articles/8724749-what-is-practice-on-chess-com)
- [Spaced repetition](https://support.chess.com/en/articles/10319322-how-does-the-spaced-repetition-scheduling-work)
- [Insights](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com)

## Prioritized roadmap

### Stage 1 — Reliability and engine confidence

- Add worker timeout, cancellation, and crash interaction coverage; malformed worker
  output now has deterministic regression coverage.
- Add install → play → save → load → analyze → retry → reopen tests.
- Stress stale generation/FEN checks and delayed bot cancellation.
- Run the opt-in real-Stockfish matrix for 800, 1000, 1200, and full strength.
- Show engine version, active profile, last failure, and analysis state in diagnostics.

### Stage 2 — Shared navigation shell

- A shared workspace stack now hosts Learn, Courses, Practice, Lessons, Insights,
  Games, Settings, Diagnostics, and Review, with a Back action returning to Play.
- Focused exercises, confirmations, and setup prompts remain dialogs.
- Keep focused exercises, confirmations, and setup prompts as dialogs.
- Preserve one active destination, back/forward behavior, keyboard navigation, and
  unsaved-work handling.
- Add rapid-switching and repeated-click GUI tests (initial coverage is in place).

### Stage 3 — Review and learning parity

- Route Learn directly to the last-opened module or first due decision.
- Distinguish authored Courses from personalized Lessons in labels and empty states.
- Link every insight to a saved game, practice item, or course decision.
- Add concise review summaries, next action, supporting evidence, and active filter counts.

### Stage 4 — Learning quality

- Keep opening, phase, and tactical transfer metrics sample-safe and inspectable.
- Apply theme and previously-failed filters to every practice entry point.
- Show per-decision mastery and completion clearly.
- Keep exercises short, forgiving, engine-verified, and progressively hinted.

### Stage 5 — Accessibility and visual polish

- Verify tab order and shortcuts with scripted Qt tests and a native Windows pass.
- Confirm focus visibility, contrast, scalable text, labels, descriptions, and
  color-independent indicators.
- Improve chart interaction, empty states, disabled-state explanations, and responsive
  board/details layout.

### Stage 6 — Deferred extensions

- Self-analysis sandbox, rich/bulk PGN import/export, multiple profiles and backup,
  additional attributed content, cached profile comparison, and optional coach speech.

## Acceptance and delivery

- Preserve the full passing suite as regression coverage.
- Add focused unit and Qt tests for each new behavior and failure path.
- Every displayed engine judgment traces to stored analysis, and every displayed line
  is legal.
- Saved games and learning progress remain readable after migrations.
- Local coaching and core practice work without an OpenAI key.
- Each roadmap finding maps to a test, implementation branch, and acceptance result.
- Work on a named feature branch, commit coherent changes, run Ruff, mypy, and the full
  suite, then merge only from a clean branch.
