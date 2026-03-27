Original prompt: rabbit hunt, deal next hand, pot need to be separated more so that all can be seen. this was broken when we added the logic for two boards (it also shows pot 1:), two boards should have a different format from 1 board so that everything fits

- Investigated the regression in `frontend/src/components/poker/PokerTable.tsx`.
- Confirmed the center-table stack currently shares the same pot/board/control positioning for single-board and double-board play, which is causing overlap on smaller mobile viewports.
- Split the center layout so single-board and double-board hands use different pot/board/control formatting.
- Tightened the mode switch to follow `board.secondary` presence instead of only `rules.extra_flop`, so one-board -> two-board -> one-board transitions stay visually stable between hands.
- Updated the two-board presentation to stack `Board 1` above `Board 2` instead of placing them side by side.
- `npm run build` passes in `frontend/`.
- Visual browser verification is still pending because the local Playwright snapshot command was blocked at the sandbox approval step after confirming the package was not installed.
