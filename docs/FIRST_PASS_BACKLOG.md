# First-Pass Product Backlog

This is the working reference for turning the current engine, review, coaching,
practice, and lesson modules into a coherent first release. Complete items roughly
in priority order, keeping each numbered item independently reviewable.

Implementation status: P0 items 1–7, P1 items 8–13, and P2 stages A–F are complete.
Keep their acceptance details as regression requirements. Stage G remains the next
roadmap item; P3 remains deferred.

## Release goal

A new user can install Stockfish, play or load a game, run a review, understand the
two or three decisions that mattered most, retry those decisions, and leave with one
useful practice task. Local coaching must remain useful when OpenAI is unavailable.

## Current assessment

The app already covers the core guided-review loop: evaluation graph and bar, move
classifications, key moments, best-line playback, retry, accuracy, opening recognition,
saved games, local coaching, weaknesses, scheduled practice, and review preferences.

The next work should address these experience gaps:

- An incorrect practice move currently restarts the entire line instead of returning
  to the current decision.
- Engine variations are too long for beginner exercises.
- A computed bot move appears immediately, making the learner's move hard to observe.
- Personalized lessons exist, but there is no authored curriculum, learning path, or
  opening trainer that deliberately follows a selected repertoire.
- Progress belongs to a complete exercise rather than each learned decision.
- Navigation lacks a focused answer to “What should I learn next?”
- Opening, tactical, course, practice, and later-game results are not yet connected.

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

## P2 — Next learning experience

### Stage A — Forgiving, short practice

**Branch:** `feature/gentle-practice-flow`

14. **Use short exercises and local correction**
    - Limit a normal exercise to two learner decisions: learner move, forced reply,
      learner move. Shorter exercises may finish after one decision.
    - Extract a reusable `TrainingSession` state machine so personal practice and
      courses share the same attempt, reply, hint, rollback, and completion rules.
    - `TrainingSession.attempt(move)` returns correctness, feedback, rollback position,
      forced reply, completion state, and the current decision index.
    - On an incorrect legal move, show a red mistake badge for 700 ms, record one
      failure, undo only that move, and return to the immediately preceding position.
      Preserve all earlier correct decisions and never expose the full solution.
    - Offer progressive hints after an error: theme, candidate move, then short line.
    - Accept verified alternatives at every learner decision.
    - Reveal the full solution only after completion or explicit `Reveal Solution`.
    - Slice newly generated personal-practice PVs to at most three plies.

**Acceptance:** A wrong move never resets a completed decision, and no normal exercise
asks the learner for more than two decisions.

### Stage B — Bot move pacing

**Branch:** `feature/bot-move-pacing`

15. **Make computer replies readable**
    - Add persistent `bot_move_delay_ms` choices of 0, 300, 600, and 900 ms, defaulting
      to 600 ms.
    - After Stockfish finishes, retain its result, preserve the learner's last-move
      highlight, and show `Stockfish is ready…` until a single-shot timer applies it.
    - Keep board input locked during calculation and the presentation delay.
    - Apply the delay to the bot's opening move when the learner chooses Black.
    - Cancel pending moves on undo, new game, load, review entry, engine failure, and
      application close. Recheck the runner generation and FEN before applying a move.

**Acceptance:** The bot replies at approximately the selected delay, and no delayed or
stale result can modify a replaced position.

### Stage C — Course platform

**Branch:** `feature/course-platform`

16. **Add a versioned, offline course system**
    - Introduce immutable `Course`, `CourseModule`, `CourseExercise`, and `MoveMastery`
      contracts. Exercise data includes FEN, learner color, authored line, alternatives,
      hints, explanations, and concept tags.
    - Package reviewed course definitions as versioned JSON. `CourseCatalog` validates
      schema versions, unique IDs, legal FENs, legal variations and alternatives, and
      the two-decision limit without database access.
    - Keep content definitions out of SQLite. Add an additive migration for enrolment,
      per-decision mastery, attempts, due dates, and the last-opened module. Stable
      content IDs and versions must preserve progress across compatible revisions.
    - Build a searchable course library filtered by opening, side, and level, plus a
      course detail screen with modules, progress, duration, and Start/Continue.
    - Build a course player with a short concept card, optional walkthrough, authored
      opponent replies, concise mistake feedback, recap, and follow-up review. Reuse
      `TrainingSession` for all board interaction.
    - Keep chess facts and lines locally reviewed and python-chess validated. OpenAI may
      later reword supplied explanations but cannot create course moves or theory.

**Acceptance:** The catalog works offline, invalid course data is rejected with a clear
content error, and a learner can start, leave, resume, and finish a course module.

### Stage D — Starter opening repertoire

**Branch:** `content/starter-opening-courses`

17. **Ship three courses for approximately 600–1400 strength**
    - **Italian Game for White:** development goals, quiet `d3` plans, the `d4` break,
      common deviations, `f7` and pin tactics, and model-game checkpoints.
    - **Caro-Kann against 1.e4:** `...c6`/`...d5`, Advance, Exchange and Classical
      structures, bishop development, tactical errors, and central breaks.
    - **Queen's Gambit Declined against 1.d4:** `...d5`/`...e6`, development and
      castling, pressure on `c4`, central breaks, pins, traps, and typical plans.
    - Give each course four modules and 8–12 micro-exercises for an initial 15–25
      minute path. Every exercise contains no more than two learner decisions.
    - Include original explanations and source attribution. Do not copy commercial
      annotations, lesson prose, artwork, or presentation.

**Acceptance:** Every packaged position and line passes catalog validation, and each
course supports walkthrough, quiz, resume, review, and authored-reply practice.

### Stage E — Adaptive daily learning

**Branch:** `feature/adaptive-learning-sessions`

18. **Turn practice into a short daily learning loop**
    - Offer up to ten exercises or approximately 15 minutes per session: 50% personal
      positions, 30% due course decisions, and 20% tactics/endgame reinforcement.
      Fill unavailable categories from other due material.
    - Schedule each learner decision independently at about 4 hours, 1, 3, 7, 14, 30,
      and 90 days. A mistake lowers only the current decision's mastery.
    - Adjust scheduling from correctness, hints, and delayed recall without adding
      streak penalties.
    - Connect later success to weakness scores and recommend the relevant module after
      repeated errors. Add theme and `Previously failed` filters.
    - Keep selection and scheduling deterministic and local; routine practice makes no
      OpenAI calls.

**Acceptance:** Session composition follows the target mix when content is available,
and mastery can be traced to individual decisions and attempts.

### Stage F — Learning home and GUI refinement

**Branch:** `feature/learning-home`

19. **Make the next learning action obvious**
    - Add a first-class **Learn** destination showing Continue Course, Practice Due,
      Review Latest Game, Weakest Theme, and one recommended next lesson.
    - Keep the board square while resizing and retain a stable board/details layout.
    - Show one verdict sentence and one takeaway by default; place longer explanation
      and variations behind `More`.
    - Preserve last-move highlights during bot pacing and animate only transitions that
      help the learner follow the position.
    - Show module progress with text and icons. Add clear selection, hover, keyboard
      focus, and empty states that lead to a useful action.
    - Add shortcuts for course navigation, retry, hint, reveal, and keyboard board use.
      Never encode meaning using color alone.

**Acceptance:** A new or returning learner can reach the recommended activity in one
action, and all new learning flows remain usable by keyboard and screen reader.

### Stage G — Progress and transfer insights

**Branch:** `feature/learning-insights`

20. **Measure whether training transfers into games**
    - Add local charts for course mastery, due reviews, phase accuracy, tactical themes,
      and opening performance.
    - Require at least five qualifying games before reporting an opening win rate.
    - Compare recent and previous periods with greater weight on recent games.
    - Track later opening departures, repeated tactical errors, delayed practice
      success, and phase-accuracy changes after related lessons.
    - Link every conclusion to games, exercises, or course decisions and recommend one
      ranked next action. Label every metric as a transparent Chess Coach estimate.

**Acceptance:** Every insight has inspectable supporting records and no small-sample
opening claim is displayed.

## P3 — Deferred extensions

21. Optional coach text-to-speech with mute, speed, and voice controls.
22. Self-analysis sandbox with multiple engine lines, arrows, editable variations,
    and play-from-position mode.
23. Rich PGN import/export with comments and variations, bulk import, and duplicate
    handling.
24. Multiple learner profiles and portable backup/restore of games and progress.
25. Comparison and time estimates for cached Quick/Standard/Deep runs; profile
    selection itself is already complete.
26. Additional attributed opening, endgame, tactic, and master-game content packs.

## Development sequence and branch policy

1. Implement Stage A and Stage B independently; neither depends on course storage.
2. Implement Stage C before any packaged course content.
3. Add Stage D only after its catalog and player are stable.
4. Build Stage E on the course and personal-practice records.
5. Add Stage F after the core learning destinations exist.
6. Build Stage G after enough persistent activity data is available.

For every branch, add focused unit and GUI integration tests, run Ruff formatting and
lint, mypy, the full test suite with coverage, and the opt-in real-Stockfish tests.
Complete a native Windows GUI pass by clicking every new control; for Stage B, measure
the visible delay near 600 ms. Commit small coherent changes and merge only from a
clean, fully validated branch.

## Planned interfaces and compatibility

- `TrainingSession.attempt(move)` owns correction and continuation state and returns a
  structured attempt result for any practice UI.
- `CourseCatalog` loads and validates packaged definitions without database access.
- `CoachRepository` will add course enrolment, decision mastery, attempt recording,
  due-review, and progress-summary operations through additive migrations.
- `UserPreferences` will add `bot_move_delay_ms` with a 600 ms default.
- Existing saved games, analysis runs, personal practice, lessons, and preferences
  must remain readable after every migration.
- Course IDs and content versions remain stable so compatible text corrections do not
  silently reset mastery records.

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

Its learning products also pair guided paths and searchable lessons with interactive
challenges, opening practice against prescribed replies, standard and punitive course
review modes, and per-move spaced repetition. Chess Coach will use the forgiving mode
by default and retain its offline-first design. See [Chess.com Lessons](https://support.chess.com/en/articles/8609703-how-do-lessons-work-on-chess-com),
[Practice](https://support.chess.com/en/articles/8724749-what-is-practice-on-chess-com),
[course settings](https://support.chess.com/en/articles/10319078-how-do-i-manage-my-course-settings),
[course scheduling](https://support.chess.com/en/articles/10319322-how-does-the-spaced-repetition-scheduling-work),
[Italian course overview](https://www.chess.com/lessons/learn-the-italian-game), and
[Insights](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com).

The daily-learning design also uses retrieval and distributed practice because testing
with feedback and repeated retrieval improve delayed retention. See the
[repeated-testing randomized trial](https://pubmed.ncbi.nlm.nih.gov/19930508/) and
[repeated-retrieval experiments](https://doi.org/10.1016/j.jml.2006.09.004).
