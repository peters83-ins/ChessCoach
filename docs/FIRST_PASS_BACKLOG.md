# First-Pass Product Backlog

This is the working reference for turning the current engine, review, coaching,
practice, and lesson modules into a coherent first release. Complete items roughly
in priority order, keeping each numbered item independently reviewable.

## Release goal

A new user can install Stockfish, play or load a game, run a review, understand the
two or three decisions that mattered most, retry those decisions, and leave with one
useful practice task. Local coaching must remain useful when OpenAI is unavailable.

## P0 — Required for a usable first pass

1. **First-run setup wizard**
   - Check Python dependencies, writable game storage, and Stockfish discovery.
   - Explain the Stockfish executable and offer Browse plus automatic detection.
   - Show OpenAI as optional, with `Not configured`, `Ready`, and `Connection failed`
     states and a test button.
   - Finish with a short playable setup rather than exposing environment terminology.

2. **OpenAI settings and safe credential setup**
   - Add a Settings dialog with model selection, readiness, connection test, and a
     link to OpenAI's API key page.
   - For the first release, guide the user to store `OPENAI_API_KEY` and
     `OPENAI_MODEL` in the ignored local `.env`; mask the key and never write it to
     SQLite, logs, screenshots, or Git.
   - Detect configuration changes without requiring source edits and explain API
     errors in plain language. Keep deterministic local feedback as the fallback.
   - Add a small usage estimate before cloud analysis and a per-game opt-in toggle.

3. **Single, obvious post-game path**
   - On game end, show `Review Game`, `New Game`, and `Save/Copy PGN` together.
   - Save first, then open review and start quick analysis with one action.
   - Preserve and clearly resume interrupted analysis.

4. **Summary-first review screen**
   - Present result, project-specific accuracy for both sides, move classification
     counts, opening name when known, and one sentence describing the game.
   - Add a horizontal evaluation graph across all plies; clicking a point jumps to
     that position. Retain the vertical current-position evaluation bar.
   - Label the accuracy metric as Chess Coach accuracy rather than Chess.com accuracy.

5. **Guided key-moment navigation**
   - Make `Next Key Moment` the primary review action while retaining previous/next,
     start/end, slider, move list, and keyboard arrows.
   - Default to the learner's important moves. Offer `My moves`, `Both sides`, and
     `All moves` without hiding why a position was skipped.
   - Show classification badges and colors directly in the move list and on the board.

6. **Explain, show, retry**
   - At each critical move, present: what was played, why it mattered, the best move,
     the core idea, and a short legal continuation.
   - Add `Show line` playback and `Retry` from the pre-move position. Hide the best
     move during retry, give progressive hints, and explain failed legal attempts.
   - Return to the exact review position after retry.

7. **Reliability and recovery**
   - Add end-to-end checks for install → play → save → load → analyze → retry → reopen.
   - Cover missing/crashed Stockfish, invalid API key, timeout/rate limit, cancellation,
     corrupt or old databases, and closing the app during analysis.
   - Add a lightweight diagnostic view with app version, database path, engine path
     and version, AI readiness, and a copyable error message without secrets.

## P1 — Makes the coach useful beyond one review

8. **Game library and navigation shell**
   - Replace the long single sidebar with clear Play, Games, Review, Practice, Lessons,
     and Settings destinations.
   - Add search/filter/sort for date, result, color, difficulty, opening, and analyzed
     state. Show analysis and practice status in each game row.
   - Confirm destructive actions and support deleting or exporting a saved game.

9. **Opening recognition**
   - Identify ECO/opening/variation from a reviewed local opening dataset.
   - Mark the last known book move and explain the first meaningful departure.
   - Aggregate results by opening while avoiding claims based on tiny samples.

10. **Weakness dashboard**
    - Show top themes, recent examples, trend, confidence, and why each weakness was
      inferred. Link every claim to positions from saved games.
    - Let users dismiss a false tag and prevent one game from dominating the profile.

11. **Practice queue**
    - Provide `Practice due today`, progress, streak-free completion counts, and review
      dates. Mix personal positions with concept reinforcement.
    - Play the opponent's forced replies automatically, accept verified alternatives,
      and show the full solution only after completion or explicit reveal.

12. **Lesson usability**
    - Turn text blocks into short steps: idea, recognition cues, annotated position,
      guided exercise, recap, and follow-up practice.
    - Resume unfinished lessons and measure later success on the same theme.

13. **User preferences and accessibility**
    - Persist board orientation, theme, piece size, analysis depth, review perspective,
      show-best-move behavior, and coach verbosity.
    - Add keyboard focus states, shortcuts, scalable text, color-blind-safe indicators,
      screen-reader labels, and sufficient contrast. Never rely on color alone.

## P2 — Useful after the first release is stable

14. Optional coach text-to-speech with mute, speed, and voice controls.
15. Self-analysis sandbox with multiple engine lines, arrows, editable variations,
    and `play this position against the bot`.
16. PGN import/export with comments and variations, bulk import, and duplicate handling.
17. Multiple learner profiles and portable backup/restore of games and progress.
18. Analysis profiles (`Quick`, `Standard`, `Deep`) with time estimates and cached
    result comparison.
19. Reviewed and attributed opening/theory content packs.

## Suggested implementation sequence

1. OpenAI settings/readiness and first-run checks.
2. Post-game `Review Game` entry point.
3. Summary screen and clickable evaluation graph.
4. Key-moment navigation and classification badges.
5. Show-line playback and retry workflow.
6. End-to-end recovery tests and diagnostics.
7. Navigation shell and game library.
8. Opening recognition, weakness dashboard, practice queue, then lessons.

## OpenAI setup for the current app

1. Sign in to the OpenAI API Platform, create a project API key, and save it when it
   is shown. ChatGPT and API billing are separate, so add API billing or credits if
   the API account does not already have them.
2. Create `.env` in the repository root. It is already ignored by Git.
3. Add:

   ```dotenv
   OPENAI_API_KEY=your_key_here
   OPENAI_MODEL=your_available_model_id
   ```

4. Restart Chess Coach. Load a saved game; the coach panel should say that OpenAI
   explanations are enabled. The API key must never be pasted into chat or committed.

Official references: [OpenAI API quickstart](https://platform.openai.com/docs/quickstart),
[API key management](https://platform.openai.com/api-keys), and
[API billing](https://platform.openai.com/settings/organization/billing/overview).

## Product reference

Chess.com's current review flow supports a highlights summary, evaluation graph,
accuracy, move classifications, guided key moves, best-line display, retry, review
perspective/settings, and self-analysis. Those interaction ideas inform this backlog;
the app will retain its own scoring, wording, visual identity, and locally verified
analysis. See [Chess.com Game Review](https://support.chess.com/en/articles/8584089-how-does-game-review-work)
and [accuracy overview](https://support.chess.com/en/articles/8708970-how-is-accuracy-in-analysis-determined).

