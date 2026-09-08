# Chess Coach

A Python 3.12+ desktop chess trainer. This first milestone is a local two-player
chessboard: both players use the same computer. It runs without an OpenAI API key,
Stockfish, an internet connection, or a database after dependencies are installed.

## Implemented

- Click a piece, then a legal destination; White starts at the bottom.
- Selected-square and legal-destination highlights, coordinates, Unicode pieces.
- Legal turns, captures, castling, en passant, and promotion to any of four pieces.
- Turn/check status, checkmate, stalemate, and automatic draws from python-chess.
- SAN move history, New Game, and Undo (one player's move at a time).
- Claim Draw for claimable repetition/fifty-move draws, including claims available
  by announcing a legal next move as determined by python-chess. These are never
  claimed automatically. Undo after a claim first withdraws the claim.
- Copy PGN to the clipboard; domain-level PGN parsing and export with FEN starts.
- Unit tests, headless Qt interaction tests, linting, formatting, and type checking.

New Game immediately resets the board. Games are held in memory; use Copy PGN
before starting another game or closing the window if you want to keep one.
The promotion dialog can be cancelled without moving the pawn.

PGN parsing loads the first standard game's mainline. Comments, variations,
original headers, and recorded resignations/agreed draws are not retained.
The parser reconstructs a playable board and derives its result from that board.
There is no PGN import/browser UI yet.

## Windows setup and launch

Install Python 3.12 or newer with the Windows Python launcher. In PowerShell,
open the repository directory. Create the environment only if it does not exist:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -r requirements.txt
python -m chesscoach.main
```

Confirm that `python --version` reports 3.12 or newer. `requirements.txt` installs
the editable application and development tools defined in `pyproject.toml`.
If activation is unavailable, run the interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m chesscoach.main
```

An activated environment also provides the `chesscoach` launcher. On Linux, create
a separate environment with `python3 -m venv .venv`, activate it with
`source .venv/bin/activate`, then use the same install/run commands. Windows and
Linux environments cannot be shared. Linux GUI use requires the Qt system
libraries and a working display; headless tests use Qt's offscreen platform.

## Development checks

From the repository root with the environment active:

```powershell
python -m pytest
python -m pytest --cov=chesscoach
python -m ruff check .
python -m ruff format --check .
python -m mypy src/chesscoach
```

To apply formatting, run `python -m ruff format .`. Integration tests instantiate
real Qt widgets, simulate clicks, and briefly run the event loop without opening
a visible window. No engine process or API requests are required.

In VS Code, select `.venv\Scripts\python.exe` with **Python: Select Interpreter**,
and configure pytest discovery in `tests`. Launch/debug the module
`chesscoach.main`; debug tests with the Python Testing panel. Local `.vscode`
settings and launch configurations are provided in this working copy but remain
ignored by Git under the existing policy. Other clones can use these same manual
steps. Exceptions remain visible in the terminal/debugger.

## Structure and boundaries

```text
pyproject.toml                 Dependencies, packaging, pytest, Ruff, mypy
requirements.txt              Editable install with development tools
.env.example                  Empty optional-service settings
src/chesscoach/
  main.py                     Application entry point
  config.py                   Explicit environment/.env configuration
  chess/
    game.py                   GUI-independent game model and status
    pgn.py                    PGN text interchange
  ui/
    chess_board.py            Board selection and promotion UI
    move_history.py           SAN table
    main_window.py            Game controls and presentation
  engine/analysis.py          Typed future engine service/results contract
  ai/client.py                Lazy OpenAI SDK factory; no requests
tests/
  unit/                       Rules, PGN, configuration, analysis results
  integration/                Offscreen desktop interaction and launch tests
```

Each package also has an `__init__.py`. python-chess is authoritative for moves,
board state, and results. Future Stockfish analysis will supply scores, best moves,
and principal variations; future LLM coaching will explain that validated data.
The LLM must never establish legality, evaluations, mate, or tactical correctness.

`EngineService` accepts board snapshots (including history), depth/time limits via
`chess.engine.Limit`, and MultiPV. A future adapter will use `STOCKFISH_PATH` and run
away from the GUI thread. No adapter, analysis execution, computer opponent,
Stockfish download, or Stockfish binary is included in this milestone.

## Optional OpenAI configuration

**You do not need to set up credentials for this milestone.** The app never
constructs an OpenAI client or sends a request on startup or during local play.
AI explanations are planned, so adding a key now does not enable a coach UI.

When implementing coaching, create an API key through the OpenAI developer
platform and configure `OPENAI_API_KEY` locally, following the
[official OpenAI quickstart](https://developers.openai.com/api/docs/quickstart).
Choose the model centrally using `OPENAI_MODEL`; no model is hard-coded here.
Do not paste credentials into source code or commit them.

The optional example contains empty values only:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=
STOCKFISH_PATH=
```

You may later copy `.env.example` to `.env` and fill it in locally. `.env` and
`.env.*` remain ignored; only the reviewed empty `.env.example` is tracked.
The factory takes `Settings.from_environment()`. Explicitly passing
`Settings.from_environment(Path(".env"))` loads that file without overriding
existing environment variables. Local chess does not read it at startup.
Calling the future-service factory without a key or model raises a clear
`ConfigurationError`; a future coach UI should display that message.

## Next milestone

Implement a configurable local Stockfish adapter and an asynchronous analysis
panel showing White-perspective evaluation, best move, and MultiPV lines for the
current position. Add adapter tests, subprocess cleanup, cancellation, and stale
result protection while keeping local chess usable when Stockfish is absent.

After that: whole-game review with transparent mistake thresholds, SQLite game
and analysis persistence, engine-grounded AI explanations, then recurring-mistake
tracking and personalized lessons/puzzles. Storage and learning modules are
intentionally deferred until their behavior is needed. No SQLite files are
created by this milestone.
