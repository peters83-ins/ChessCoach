# Chess Coach Engine, GUI, and Workflow Audit

Updated: 2026-09-09

This is the canonical audit and development roadmap. It consolidates the former
first-pass backlog, UX audit, and roadmap status documents. Completed work remains
regression scope; the staged backlog below is the active queue.

## Baseline

- Python 3.12+, python-chess, Stockfish, PySide6, SQLite, and optional OpenAI feedback.
- Stockfish and python-chess are authoritative for legality, evaluation, and tactics.
- OpenAI is an optional explanation layer and must only receive verified facts.
- Baseline validation: 197 passed, 8 skipped on the Windows Python module test run.
- Real-Stockfish tests are opt-in through `CHESSCOACH_TEST_STOCKFISH`.
- Stage 0 audit harness now covers every primary destination and the visible
  non-destructive controls in three repeated offscreen passes. The current full
  run is 197 passed, 8 skipped, with aggregate coverage still at 88%.
- Completed: P0/P1, P2 Stages A–F, modern GUI pass, adaptive practice, course catalog,
  review insights, opening/phase transfer metrics, supporting-position links, themed
  practice links, related-course links, Stage 3 direct learning routing, Stage 4
  per-decision mastery display and persistence, Stage 5 accessibility polish, and
  Stage 6 extensions.

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

Stage 0 baseline work is complete on `audit/baseline-harness`; the remaining items
below are the final reliability checks for this release.

- Add worker timeout and cancellation interaction coverage; malformed output and
  startup-process crashes now have deterministic regression coverage.
- Add install → play → save → load → analyze → retry → reopen tests.
- Stress stale generation/FEN checks and delayed bot cancellation.
- Run the opt-in real-Stockfish matrix for 800, 1000, 1200, and full strength.
- Show engine version, active profile, last failure, and analysis state in diagnostics.

The audit harness emits structured `AuditReport`/`AuditFinding` JSON so each future
stress run can be attached to the finding table without relying on console prose.

Engine and coaching runners now expose explicit idle/searching/ready/cancelled/failed/
closed states and preserve the last worker error for diagnostics. Focused tests cover
stale generation rejection, cancellation invalidation, malformed output, and startup
crashes. The sandbox also has deterministic tests for legal output, terminal positions,
and stale FEN results. Timeout and real-Stockfish matrix coverage remain opt-in follow-up
checks because the normal CI path uses fake engines.
The recovery suite also verifies a saved match can be reopened in a fresh window with
its validated move history and review position intact. Full install and real-engine
matrix execution remain environment-dependent checks.
Timeout exceptions now have a deterministic retryable-error regression test. The only
remaining Stage 1 execution item is the opt-in real-Stockfish matrix on a machine with
an installed executable.
Settings now selects a persisted learner profile, and the selected profile flows through
coaching records, practice, courses, lessons, learning home, insights, and weakness
views while defaulting safely to the existing local profile.

### Stage 2 — Shared navigation shell

- A shared workspace stack now hosts Learn, Courses, Practice, Lessons, Insights,
  Games, Settings, Diagnostics, and Review, with a Back action returning to Play.
- Focused exercises, confirmations, and setup prompts remain dialogs.
- Keep focused exercises, confirmations, and setup prompts as dialogs.
- Preserve one active destination, back/forward behavior, keyboard navigation, and
  unsaved-work handling.
- Add rapid-switching and repeated-click GUI tests (initial coverage is in place).

The typed workspace navigator, bounded Back/Forward history, page reuse, and
conservative Qt shutdown cleanup are implemented and covered by unit and stress tests.
Primary destinations now use a compact vertical rail with exclusive active-state
selection; Back and Forward remain separate keyboard-accessible actions.

### Stage 3 — Review and learning parity (complete)

- Learn routes directly to the first due course decision, then the last-opened module,
  and finally the first available course.
- Courses and personalized Lessons are explicitly distinguished in navigation, library
  copy, and empty-state messaging.
- Insights link themes to supporting saved positions, themed practice, and matching
  authored course content; local metrics retain sample-size safeguards.
- Review summaries expose a next action and supporting evidence, while Games and Courses
  show active filter summaries and result counts.
- Limited-strength play uses weighted, legal variation between equivalent engine-ranked
  moves; full-strength analysis and review remain deterministic.

### Stage 4 — Learning quality (complete)

- Opening, phase, and tactical transfer metrics remain local, sample-safe, and linked
  to inspectable game or practice evidence.
- Practice queue entry points expose theme and previously-failed filters with counts.
- Course detail and player views show per-decision level, attempts, errors, hints, and
  exercise completion; every learner decision is persisted, including intermediate
  correct moves.
- Training sessions report the decision that was answered, preserve rollback state,
  accept verified alternatives, keep lines short, and provide progressive hints.
- Learn now presents one prominent recommended action while retaining secondary browse
  actions. Recommendations follow due practice, unfinished course work, latest-game
  review, weakness, then course availability.

### Stage 5 — Accessibility and visual polish (complete)

- Scripted Qt coverage verifies primary tab order, evaluation-graph keyboard navigation,
  accessible names/descriptions, visible focus styling, and square board sizing.
- Disabled primary actions explain what the learner must do next, and empty filtered
  practice/saved-game states expose actionable tooltips.
- Evaluation graph critical moves use red diamond markers plus accessible text, so the
  chart does not rely on color alone. The evaluation bar exposes its White/Black meaning.
- The Windows Qt test run verifies the keyboard and accessibility contract in the
  supported desktop runtime; manual screen-reader testing remains an operational check
  for release machines rather than an untested code path.
- The visual-system slice now defines typography, focus/disabled/selected states,
  styled scrollbars, sliders, progress bars, table rows, tooltips, and a collapsed
  Tools & data group so the Play workspace presents fewer secondary controls.

### Stage 6 — Extensions (complete)

- **Complete:** bulk PGN import/export. The parser accepts every legal standard mainline
  in a document, rejects empty/illegal/variant games, imports each game through the
  existing validated SQLite save path, and exposes Import PGN and Export All controls.
  Imported games receive new IDs and preserve legal move/FEN histories.
- **Complete:** self-analysis sandbox. The app provides an offline legal board, FEN
  loading, current-position copying, and explicit status feedback without treating
  prose or an LLM as an engine authority.
- **Complete:** profile and portability foundations. Coach storage supports creating
  and deleting non-default learner profiles, cached profile-run summaries, and atomic
  backup/restore of the games and coaching SQLite databases. Main-window Backup Data
  and Restore Data controls use the validated archive service.
- **Complete:** additional content-pack loading. `CourseCatalog.from_directory` combines
  versioned, python-chess-validated JSON packs and rejects duplicate course IDs.
- **Complete:** optional coach speech. The coach panel offers a read-aloud control when
  Qt's platform speech backend is available and remains local-only otherwise.
- **Complete:** profile selection is threaded through settings, coaching, practice,
  lessons, courses, insights, and learning-home recommendations. The sandbox now
  supports optional Stockfish analysis with a bounded ELO control, concise legal SAN
  output, explicit loading/cancel/error states, terminal-position handling, and FEN
  checks that reject stale results.

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
- WSL diagnostics use `scripts/run_tests_wsl.sh`, which creates an isolated Linux
  `.venv-wsl` and sets Qt to offscreen. The Windows `.venv` must be run from PowerShell,
  because launching its executables through WSL interop is unsupported in some hosts.

## Finding-to-test status

| Finding | Current regression coverage | Remaining acceptance check |
| --- | --- | --- |
| AUD-002 | Audit stress, worker failure, sandbox, and recovery tests | Raise aggregate coverage to 90% when the native test run is available |
| AUD-003 | Fake-engine startup, malformed-output, timeout, and retry tests | Run the real Stockfish 800/1000/1200/full matrix |
| AUD-004 | Generation/FEN rejection, delayed cancellation, and fresh-window recovery tests | Repeat the matrix on native Windows during release verification |
| AUD-006 | Qt accessible-name, focus, and keyboard contract tests | Complete the documented Windows screen-reader pass |
| AUD-007 | Sample safeguards and supporting evidence links | Add richer chart interaction coverage |
| AUD-008 | Responsive board, scrollbar, focus, and empty-state tests | Review chart readability at supported scaled-text sizes |
