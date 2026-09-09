# Chess Coach Roadmap Status

This document consolidates `FIRST_PASS_BACKLOG.md` and `UX_AUDIT_2026-09.md`.
Completed items remain regression requirements; the unchecked work below is the
active development queue.

## Completed

- P0 1–7: setup, OpenAI configuration, post-game flow, summary review, key moments,
  explain/show/retry, and recovery diagnostics.
- P1 8–13: game library, opening recognition, weakness dashboard, practice queue,
  lesson usability, preferences, and accessibility foundations.
- P2 Stages A–F (14–19): forgiving training sessions, paced bot replies, offline
  course platform, three starter opening courses, adaptive scheduling, mixed daily
  practice, Learn home, direct course resume, navigation clarity, and modern GUI theme.
- UX audit fixes: direct course resume, mixed daily practice, destination labels,
  filter/result counts, modeless destination navigation, fresh-database empty state,
  and modern visual styling.

## Outstanding, grouped by implementation stage

### Stage G — Learning insights (`feature/learning-insights`)

- Add local charts for course mastery, due reviews, phase accuracy, tactical themes,
  and opening performance.
- Require five qualifying games before showing opening win-rate conclusions.
- Compare recent and previous periods with greater weight on recent games (implemented
  in the Insights panel; requires three games per period).
- Measure transfer from persisted practice attempts: the Insights panel now reports
  theme success before and after practice when each side has five observations;
  opening departure now compares reviewed-line coverage in recent and earlier games;
  game-phase transfer compares analyzed moves when each phase has enough data.
- Link theme insights to supporting game positions through the review action; extend
  links to exercises and course decisions as those views gain evidence records.
  Recommend one ranked next action and label metrics as project-specific Chess Coach
  estimates.
- Add unit tests for aggregation, sample thresholds, recency weighting, transfer
  metrics, and recommendation ranking, plus a local insights panel.

### Remaining UX refinement

- Replace the remaining destination dialogs with a shared content area where practical;
  keep focused exercises and confirmations as dialogs.
- Add a visible session completion state and theme/previously-failed filters to daily
  practice (implemented in the Practice Queue; failed-item IDs are stored locally).
- Add explicit screen-reader names and descriptions across course library, player,
  and board controls; continue native Windows keyboard and screen-reader verification.

### Deferred P3

- Text-to-speech coach output.
- Self-analysis sandbox and play-from-position mode.
- Rich/bulk PGN import and export.
- Multiple learner profiles and backup/restore.
- Comparison of cached analysis profiles and additional attributed content packs.

## Delivery policy

Work on each group in a named branch, add useful unit/Qt tests, run Ruff, mypy, and
the full suite, then merge only from a clean branch. Keep OpenAI optional and keep
analytics local.
