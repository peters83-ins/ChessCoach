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

Install a compatible local Stockfish executable separately, outside the repository.
In the app, choose **White or Black**, choose a difficulty, **Browse** to the
executable, then **Start Match**. Selecting Black flips the board and Stockfish
plays first. Alternatively, choose **Local two-player** without an engine.

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
  best move. Positive scores favor White; signed mate scores identify the winning
  side. Analysis is full-strength; opponent moves use the selected difficulty.
- Bot tiers target approximately 1400, 1800, or 2200 Elo. Targets are clamped to the
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

## Saved games

Completed human-versus-bot matches save automatically. **Save Match** also saves
unfinished games and retries failed saves. New Game and normal window close save
an unfinished bot match before leaving it. Failed saves preserve the board and
block reset/close so you can retry. There is no crash-recovery autosave per move.

SQLite lives in Qt's per-user local application-data directory as `games.sqlite3`.
The Save Match tooltip and save confirmation show the exact path. Local two-player
games are not stored automatically; use Copy PGN for those.

Each record contains a match UUID, player color, actual bot Elo, result, full PGN,
UCI and SAN move lists, the initial FEN plus a FEN after every ply, UTC move
timestamps, and start/save/end timestamps. Unfinished matches have result `*` and
no end timestamp. Repeated saves update the same record transactionally.

The Python persistence API is `GameDatabase(path).save_game(game_data)`, accepting
`GameData`; `BotMatch.save(database)` builds that record from a game and its metadata.
There is no saved-game browser or resume UI yet. Domain PGN parsing loads the first
standard mainline; comments, variations, headers, and recorded resignations/agreed
draws are not retained.

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
  chess/                  Game rules, PGN, geometric attack queries
  engine/
    analysis.py           Evaluation and candidate-line contracts
    stockfish.py          Local UCI adapter and difficulty control
    worker.py             Cancellable background searches
  ui/
    main_window.py        Match flow and controls
    match_setup.py        Color, difficulty, executable selection
    chess_board.py        Board and orientation
    piece_assets.py       Cached SVG piece rendering
    attack_overlay.py     Toggleable, mouse-transparent arrows
    move_history.py       SAN table
  storage/
    database.py           GameData and transactional save_game API
    match.py              Match identity and timestamps
  ai/client.py            Future OpenAI client factory; no requests
tests/unit/              Chess, attack, engine, configuration, storage tests
tests/integration/       GUI flows, workers, optional real Stockfish tests
```

python-chess and Stockfish are authoritative for chess mechanics and analysis.
OpenAI coaching, game review, lessons, and a saved-game browser remain unimplemented.
No API key is needed for the implemented features. Piece artwork attribution is in
[THIRD_PARTY.md](THIRD_PARTY.md); SVGs are rendered from the existing python-chess
dependency, not downloaded separately.
