# Standard FPL Browser-Local Report Viewer

Last reviewed: 23 August 2026

## Purpose

The public `standard-fpl-viewer.html` asset provides hands-on visual testing of a private Standard FPL report without publishing that report to GitHub Pages. It is a temporary personal testing surface, not the future authenticated Standard FPL mode in the shared dashboard.

The hosted page contains only HTML, CSS and JavaScript. The manager selects the locally generated `data/private/standard-fpl-poc.json` through the browser file picker. The file is parsed and rendered in the current tab's memory and is never sent to a report endpoint.

## Testing workflow

1. Use the [browser-local snapshot helper](STANDARD_FPL_SNAPSHOT_HELPER.md) to download the sanitized current-team snapshot.
2. Place it at `data/private/current-team.json`.
3. Configure `FPL_STANDARD_ENTRY_URL` and `FPL_STANDARD_PRIVATE_SNAPSHOT`, then run `fpl-toolkit --mode standard-fpl`.
4. Open `https://thatsivore.github.io/draft_toolkit/standard-fpl-viewer.html`.
5. Choose or drop `data/private/standard-fpl-poc.json` onto the viewer.
6. Review the hold/transfer decision, Recommended XI, captaincy, four-Gameweek outlook, legal transfer candidates and frozen outcomes.
7. Press **Clear private report** or refresh the page to remove the rendered state.

## Enforced boundary

The viewer:

- performs no `fetch`, XMLHttpRequest, WebSocket, beacon or other report-network request;
- does not use local storage, session storage, IndexedDB or cookies;
- rejects reports containing entry IDs, internal owner identifiers or credential-shaped fields;
- accepts only a `standard_fpl` private report with the lineup, decision and squad-outlook contracts;
- builds the interface with DOM text nodes rather than interpreting report strings as HTML;
- stores no report in the repository or deployed Pages assets; and
- remains unlinked from the public Draft dashboard until secure private Standard report delivery exists.

Team name, squad, finances and transfer plans are still private information while displayed on screen. The browser and operating system remain part of the user's local trust boundary.

## Limitations

GitHub Pages cannot run the Python analysis or protect a hosted private report. The viewer therefore does not remove the local command step and cannot automatically refresh after FPL changes. A secure shared mode selector still requires an authorized private report source and server-side access control.

The viewer validates the report shape but does not reproduce model calculations in JavaScript. The Python report remains the source of truth, which avoids creating a second analysis implementation that could drift from the tested collector.
