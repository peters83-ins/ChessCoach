# Chess Coach

Python 3.12+ / PySide6 desktop chess with local Stockfish play and SQLite match
saving. No OpenAI credentials or network connection are needed during play.

## Run on Windows

From the repository directory in PowerShell, use the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m chesscoach.main
```

If `.venv` does not exist, create it first with `py -3 -m venv .venv` using Python
3.12 or newer. Optional activation: `.\.venv\Scripts\Activate.ps1`. Once activated,
`python -m chesscoach.main` also launches the app.

On first launch, a setup guide checks the saved-game folder, looks for Stockfish,
and offers optional OpenAI configuration. The same fields remain available through
**Settings**. The API key is masked and stored only in the ignored local `.env`.
Use **Diagnostics** to copy the app version, database path, engine details, AI
readiness, and latest sanitized error.

Install a compatible local Stockfish executable separately, outside the repository.
In the app, choose **White or Black**, choose a difficulty, **Browse** to the
executable, then **Start Match**. Selecting Black flips the board and Stockfish
plays first. Alternatively, choose **Local two-player** without an engine.

The “Stockfish executable” is the engine program (`stockfish.exe` on Windows),
not a credential or a PGN file. The app automatically checks PATH and its per-user
engine folder: `%LOCALAPPDATA%\ChessCoach\engines\stockfish.exe` on Windows, or
`$XDG_DATA_HOME/ChessCoach/engines/stockfish` on Linux (defaulting to
`~/.local/share/ChessCoach/engines/stockfish`). The official download link is shown
in setup. Extract the download before choosing the executable.

Before a match starts, clicking a piece previews its legal destinations. Moving
requires **Start Match**; the status explains this directly. If no engine is
selected, the button says **Choose Stockfish first**. Local two-player mode needs
no engine. During a bot turn, piece input stays locked until the computer replies.

To prefill the engine path, set `STOCKFISH_PATH` in your environment or local `.env`.
You can copy `.env.example` to `.env`; environment variables take precedence.
`.env`, virtual environments, databases, and generated output remain ignored.
No Stockfish binaries or credentials are committed.

## Gameplay

- Filled white/black SVG pieces, square selection, legal destination highlights,
  and SAN move history. Click a piece, then its destination.
- Castling, en passant, captures, all four promotions, check, checkmate, stalemate,
  and automatic draws are handled by python-chess.
- **Show attacks on enemy pieces** toggles red arrows for both sides. These are
  geometric attacks, including pinned pieces, not guaranteed legal/winning captures.
  En passant is not shown because its destination is empty.
- Stockfish supplies a current-position evaluation from White's perspective and a
  best move. The vertical bar beside the board expands the winning color toward
  its opponent and flips with the board orientation. Positive scores favor White;
  signed mate scores identify the winning side. Analysis is full-strength; opponent
  moves use the selected difficulty.
- Beginner practice tiers are labelled approximately **800, 1000, and 1200**.
  They deliberately sample weaker Stockfish-ranked legal moves, allowing more
  errors at easier levels. They are **uncalibrated practice settings**, not native
  Stockfish Elo values or measured human ratings; they are never silently replaced
  with the engine's minimum rating. The selected practice label is saved with the match.
- Native bot tiers target approximately 1400, 1800, or 2200 Elo. Targets are clamped to the
  installed engine's advertised range; the actual target is displayed and saved.
  These are approximate engine settings, not guaranteed human ratings. See the
  [Stockfish difficulty documentation](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html#how-do-skill-level-and-uci_elo-work).
- Engine work runs in background threads. Human input is blocked on the bot's turn;
  changing games, undoing, or closing cancels searches and rejects stale results.
- **Undo** takes back to your previous decision in a bot match, or one ply in local
  mode. Completed bot matches cannot be undone. **New Game** returns to setup.
- **Claim Draw** enables python-chess repetition/fifty-move claims on your turn,
  including claims available through a legal next move. Automatic draws need no claim.
- Engine errors appear in the panel. Use **Retry Engine**, or **New Game** to change
  the executable. A missing engine never silently switches to a different opponent.
- **Copy PGN** exports the current game to the clipboard.

Searches use 0.2 seconds for evaluation and 0.3 seconds for opponent moves, plus
startup overhead. These short searches provide practical estimates, not exhaustive
analysis. Difficulty limiting may intentionally choose a weaker move than the
full-strength analysis recommendation.

Beginner searches rank legal moves using MultiPV, capped at 12,000 nodes and 0.3
seconds. Move selection uses a score-weighted distribution with position/level
seeding; identical candidate scores and positions yield identical choices.
Engine scores themselves remain unchanged. Full-strength position analysis is
kept separate from weakened opponent move selection.

## Saved games

Completed human-versus-bot matches save automatically. **Save Match** also saves
unfinished games and retries failed saves. New Game and normal window close save
an unfinished bot match before leaving it. Failed saves preserve the board and
block reset/close so you can retry. There is no crash-recovery autosave per move.

SQLite lives in a `games` folder under Qt's per-user local application-data
directory as `games/games.sqlite3`. The folder is created automatically before
the database is opened. On this Windows account, the default location is:

```text
C:\Users\jadon\AppData\Local\Chess Coach\games\games.sqlite3
```

The application displays the active path below move history so it can be selected
and copied.
The Save Match tooltip and save confirmation show the exact path. Local two-player
games are not stored automatically; use Copy PGN for those.

Each record contains a match UUID, player color, actual bot difficulty, result,
full PGN, UCI and SAN move lists, the initial FEN plus a FEN after every ply, UTC move
timestamps, and start/save/end timestamps. Unfinished matches have result `*` and
no end timestamp. Every ply is also stored as a row in `game_moves`, with UCI,
SAN, before/after FEN, and timestamp. Repeated saves replace that match's move rows
transactionally, preserving the complete current history without duplicates.

The Python persistence API is `GameDatabase(path).save_game(game_data)`, accepting
validated `GameData`; it returns a `SaveResult` with a `success` boolean and a short
error on failure. Validation requires moves, matching timestamps, player color,
and positive bot difficulty. `BotMatch.save(database)` builds the record.
Use **Games** or **Load Saved Game** to search, filter, and sort matches by date,
result, color, difficulty, opening, and analysis state. The library shows practice
counts and supports confirmed deletion and PGN export. Loading opens a read-only
analysis view at the final move.
Use the first, previous, next, last, and slider controls to visit any ply. The board
shows the selected position, with the played move in blue and Stockfish's best move
in purple. The details panel shows both moves in SAN and the evaluation before the
played move. Results are cached by position while the game remains open. **New Game**
exits that view. Domain PGN parsing loads the first standard mainline; comments,
variations, headers, and recorded resignations/agreed draws are not retained.
Databases from the previous parent-folder location are also listed.

## Development

```powershell
python -m pytest
python -m pytest --cov=chesscoach
python -m ruff check .
python -m ruff format --check .
python -m mypy src/chesscoach
```

The suite uses real offscreen Qt widgets and deterministic engine doubles. To also
run real Stockfish process/GUI tests, set `CHESSCOACH_TEST_STOCKFISH` to your local
executable before running pytest. Those tests skip when the variable is unset.

Linux development requires a separate Linux virtual environment and Qt system
libraries; do not reuse a Windows `.venv`. VS Code: select the project's Python
interpreter and discover pytest in `tests`. Ignored local `.vscode` settings include
application and pytest launch configurations.

```text
src/chesscoach/
  main.py, config.py       Launch and environment configuration
  preferences.py          Persistent display, review, and analysis choices
  chess/                  Game rules, PGN, opening recognition, attack queries
  engine/
    analysis.py           Evaluation and candidate-line contracts
    stockfish.py          Local UCI adapter and difficulty control
    practice.py           Approximate beginner move selection
    discovery.py          Per-user engine/PATH discovery
    worker.py             Cancellable background searches
  coach/                  Analysis, facts, feedback, reports, practice, lessons
  ui/
    main_window.py        Match flow and controls
    match_setup.py        Color, difficulty, executable selection
    chess_board.py        Board and orientation
    evaluation_bar.py     Graphical White/Black engine evaluation
    game_review.py        Saved-game navigation and engine comparison
    coach_panel.py         Full-game report, feedback, practice, and lessons
    learning_center.py     Weakness dashboard and scheduled practice queue
    piece_assets.py       Cached SVG piece rendering
    attack_overlay.py     Toggleable, mouse-transparent arrows
    move_history.py       SAN table
  storage/
    database.py           GameData and transactional save_game API
    coach.py              Versioned coaching persistence and analysis cache
    match.py              Match identity and timestamps
  ai/client.py            Future OpenAI client factory; no requests
tests/unit/              Chess, attack, engine, configuration, storage tests
tests/integration/       GUI flows, workers, optional real Stockfish tests
```

python-chess and Stockfish are authoritative for chess mechanics and analysis.
No API key is needed for local coaching or gameplay. Piece artwork attribution is in
[THIRD_PARTY.md](THIRD_PARTY.md); SVGs are rendered from the existing python-chess
dependency, not downloaded separately.

## AI coach

Load a saved game and choose **Analyze Full Game**. Chess Coach scans every move,
deepens critical positions, grades the player's decisions, and shows grounded local
feedback in the review panel. The report includes project-specific accuracy, phase
results, turning points, recurring weaknesses, practice positions, and tailored
lessons. Analysis and feedback are stored in the same SQLite database and reused.

After a bot game ends, **Review Game** saves and opens it, then starts analysis in
one action. The review begins with a whole-game summary and clickable evaluation
graph. **Next Key Moment** visits the learner's turning points; arrow keys and the
move list provide direct navigation. **Show Best Line** replays the cached engine
variation, while **Retry Move** hides the answer and returns to the exact review
position afterward. Cancelled or failed analysis can be resumed with cached
positions intact.

The local coach works without credentials. To improve the wording for critical
player moves, set both `OPENAI_API_KEY` and `OPENAI_MODEL` in the ignored `.env`.
You can enter these through **Settings**, choose **Test OpenAI**, then opt in for a
particular review with **Use OpenAI for critical-move explanations**.
Only selected positions, legal moves, engine lines, classifications, and extracted
evidence are sent; full PGNs and API keys are not stored or transmitted by the
coaching pipeline. Invalid or unavailable AI output falls back to local feedback.
Cloud requests batch a few critical positions, cap principal variations and output,
and reuse cached feedback to limit token use.

The navigation toolbar provides **Play**, **Games**, **Review**, **Practice**,
**Lessons**, and **Settings**. The weakness dashboard links each inferred theme and
its engine evidence to saved examples. Practice schedules personal positions,
automatically plays forced replies, and records later success against the same theme.
Lessons resume at the last step and link back to verified practice. Settings persist
board orientation and contrast, piece and text size, review perspective, best-move
visibility, coaching detail, and Quick/Standard/Deep analysis depth.
See [AI coach architecture](docs/AI_COACH.md) for scoring and extension contracts.
The prioritized [first-pass product backlog](docs/FIRST_PASS_BACKLOG.md) is the working
reference for onboarding, review navigation, practice, lessons, and release readiness.
