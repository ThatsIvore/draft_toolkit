# Standard FPL Browser-Local Snapshot Helper

Last reviewed: 22 August 2026

## Status

The first personal-use two-stage exporter is implemented as a standalone GitHub Pages helper:

- `public/standard-fpl-snapshot-helper.html` is the installer and user guide;
- `public/standard-fpl-snapshot-helper.js` loads the readable bookmarklet source;
- `public/standard-fpl-snapshot-bookmarklet.js` performs the same-origin capture; and
- `tests/test_standard_fpl_snapshot_helper.py` enforces its origin, network, storage, output and read-only boundaries.

It is deliberately not linked from or loaded by `public/index.html`. The existing Draft/H2H dashboard remains the default product shell and receives no Standard FPL state.

This is a personal technical proof, not paid onboarding. It depends on the official site's rendered labels and markup and may need maintenance when that UI changes.

## User flow

1. Open `standard-fpl-snapshot-helper.html` and drag **Capture FPL snapshot** to the browser's bookmarks bar.
   Wait for the installer to say it is ready. The installer URL-encodes the long helper source so Chrome preserves its line and comment boundaries. Delete and reinstall an older bookmark if clicking it produces no message.
2. Sign in manually on `fantasy.premierleague.com`; the helper never participates in sign-in.
3. On **Pick Team**, select **List** and **Selling Price**, ensure there are no unsaved lineup changes, and click the bookmark.
4. The first pass validates and captures the squad, lineup order, captaincy, prices and chip state, then navigates to **Transfers**.
5. With no pending transfers, click the same bookmark again. The second pass reads free transfers, briefly opens the signed-in entry's visible public Transfer History page for its finance summary, closes that window, validates the complete contract and downloads `standard-fpl-current-team.json`.
6. Move the file to the gitignored `data/private/current-team.json` path and set `FPL_STANDARD_PRIVATE_SNAPSHOT` before running `fpl-toolkit --mode standard-fpl`.

The helper stops without exporting when expected state is missing or ambiguous. It never submits a lineup, transfer or chip action.

## Two-stage data flow

| Stage | Page | Accepted fields | Result |
|---|---|---|---|
| 1 | `/en/my-team` | Decision Gameweek; 15 visible player name/club/position tuples; lineup order; captain flags; purchase/selling prices; four chip states | Names are joined to stable IDs through the unauthenticated public bootstrap. Only sanitized IDs and contract fields enter one helper-owned session value. |
| 2 | `/en/transfers` plus the visible `/en/entry/{public-entry}/transfers` summary | Matching Decision Gameweek; free-transfer allowance; bank; squad value; confirmed Gameweek transfers | A temporary same-origin popup supplies the visible finance summary, then closes. The complete `standard-fpl-private-snapshot-v1` payload is validated and downloaded locally. The staged value is removed. |

Player names and clubs exist only long enough in first-pass memory to perform the public bootstrap join. They are not written to the staged value or final file.

## Security and privacy boundary

The helper:

- runs only when `location.origin` exactly matches `https://fantasy.premierleague.com`;
- makes one programmatic data request, to the unauthenticated `/api/bootstrap-static/` player feed, with browser credentials explicitly omitted;
- temporarily opens the entry's ordinary public Transfer History route in a same-origin popup, reads only its rendered finance summary, and closes it;
- does not call `/api/my-team/` or any other protected endpoint;
- does not read passwords, cookies, authorization headers, tokens, account/profile state or existing browser-storage keys;
- reads and writes only its exact namespaced `sessionStorage` key;
- removes that key after a successful download and after any handled failure;
- neither stores nor exports the public entry number present in that visible route, and emits no account identifier, player name or club; and
- checks that Save Team and Make Transfers are disabled rather than pressing either control.

The downloaded file remains private and must never be placed under `public/` or committed. Existing server-side contract validation is still required; browser validation is defence in depth, not a replacement.

## Fail-closed checks

The first pass rejects the capture unless it sees:

- the Pick Team route and exact list table;
- all `CP`, `PP` and `SP` columns;
- 15 players in a 2/5/5/3 squad;
- exactly 11 starters followed by four substitutes;
- one starting captain and one starting vice-captain;
- complete positive purchase/selling prices;
- an unambiguous public-bootstrap match for every player; and
- a recognized state for Bench Boost, Triple Captain, Wildcard and Free Hit.

The second pass rejects missing or mismatched Gameweek state, pending transfers, malformed staged state, missing finance/transfer fields, non-integer contract values, duplicate players/positions, invalid captaincy or unexpected output fields.

## Current limitations

- The DOM adapter is specific to the official interface observed on 22 August 2026.
- The helper expects English page labels.
- It targets laptop browsers with a bookmarks bar; mobile installation is not yet designed.
- Its chip numbering follows the documented 2026/27 rule: set 1 through Gameweek 19 and set 2 afterward. Rules and UI behavior must be reviewed before another season.
- A page change can stop capture even when the underlying FPL data remains available. This is intentional: guessing would create misleading transfer advice.
- Popup-blocker handling is fail-closed; the user may need to allow the same-site Transfer History window.
- Distribution, browser-extension review, automatic ingestion and polished recovery UX are not implemented.

## Commercial consequence

The helper proves that Ivor can produce a useful private current-team file without handing credentials to the toolkit. It does not remove the commercial integration gate. Selling automatic access still depends on Premier League permission, a registered client/data path and a hosted account-bound backend; a fragile bookmarklet is not an acceptable substitute for that onboarding.
