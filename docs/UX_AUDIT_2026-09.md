# Chess Coach UX Audit

Hands-on Qt pass completed 2026-09-09 using the desktop application and offscreen
Qt interaction checks. The audit covered board selection, rapid game controls,
course search/filtering, Learn, Settings, saved-game states, practice rollback, and
a long legal move list.

## Observed behavior

- Selecting a starting pawn highlights two legal destinations correctly.
- Repeated New Game, Undo, and Claim Draw actions completed without exceptions.
- The Courses library displays the three starter courses; title search, side, and
  rating filters update results immediately. Empty results are clearly stated.
- Learn opens with a useful recommendation. For a new local profile it recommends a
  starter course and disables unavailable practice/review/weakness actions.
- Settings masks the API key by default. The reveal toggle works, and bot-delay
  choices are exactly 0, 300, 600, and 900 ms.
- An empty Games library disables Open, Delete, and Export and shows the database path.
- An incorrect course move shows a mistake state and returns to the same decision after
  the correction delay.
- A long legal history rendered and scrolled to the end without an interaction error.

## Usability issues

- Navigation now exposes both **Lessons** and **Courses**, plus **Learn**. Their roles
  are not explained, so a new learner may not know whether to open a personalized
  lesson, an authored course, or Learn first.
- Learn's Continue course action opens the course library rather than the specific
  enrolled module. This adds an extra selection step to the recommended path.
- The daily practice queue still presents personal practice records; due course
  decisions are available to the data layer but are not yet shown as one mixed daily
  session in the practice dialog.
- Course filtering has no visible count or active-filter summary, making an empty
  result after combining search, side, and rating filters easy to misread.
- Modal dialogs require closing before switching to another destination. Rapid view
  switching therefore feels slower than the toolbar suggests.

## Next development plan

1. Make Learn the canonical entry point and route Continue directly to the last-opened
   course module or first due decision.
2. Merge personal, course, and concept items into the visible Practice due-today flow;
   show session progress and the selected mix.
3. Clarify Lessons versus Courses with subtitles, destination labels, and a first-run
   choice that explains the difference.
4. Add active-filter summaries and result counts to course and game libraries.
5. Replace destination-blocking modal navigation with a shared content area where
   practical, retaining dialogs for focused exercises and confirmations.
6. Add GUI tests for rapid navigation, filter combinations, course resume, and daily
   session completion before starting Stage G insights.
