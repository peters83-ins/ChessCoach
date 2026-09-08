# Chess Coach Development Instructions

## Project purpose

Chess Coach is a desktop chess training application.

It combines:

- python-chess for chess rules and PGN/FEN handling
- Stockfish for objective chess analysis
- OpenAI models for human-readable coaching
- PySide6 for the desktop interface
- SQLite for persistent player data

## Architecture

Keep chess engine analysis separate from LLM interpretation.

The LLM must never be treated as the authoritative source for:

- legal moves
- engine evaluation
- checkmate detection
- tactical correctness

Stockfish and python-chess are authoritative for chess mechanics.

## Development rules

- Python 3.12+
- Type hints for public functions
- Avoid large monolithic files
- Add tests for game logic and analysis
- Never hard-code API credentials
- Use environment variables for secrets
- Do not commit .env
- Prefer small, reviewable commits
- Run tests before completing a task
