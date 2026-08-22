# Standard FPL Current-Team Authentication Discovery

Last reviewed: 22 August 2026

## Decision

The toolkit cannot responsibly add a **Sign in with FPL** button to its current GitHub Pages application by reusing Fantasy Premier League's own sign-in client.

Two independent controls block that design:

1. the Premier League identity service rejects the toolkit's callback URL because it is not registered for FPL's OAuth client; and
2. the protected current-team API does not grant the toolkit's GitHub Pages origin cross-origin access.

The login technology itself is conventional OpenID Connect authorization-code flow with PKCE. That does not make FPL's registered client reusable by an unrelated application. A supported hosted integration would require the Premier League to approve the use, register a client and redirect URI for the toolkit, and permit the relevant data access. The separate data-rights and commercial-permission gate in `COMMERCIAL_FEASIBILITY.md` also remains in force.

The toolkit must not collect a Premier League email or password, proxy the official login form, ask a user to paste a session token, copy browser cookies, or reuse FPL's public client identifier with an unregistered redirect.

## What was observed

The following findings were reproduced against the live official services on 22 August 2026. No account credentials or authenticated response bodies were collected.

| Question | Observation | Consequence |
|---|---|---|
| How does the official FPL web app sign in? | Its published application configuration uses the Premier League account issuer and authorization-code flow with PKCE, requesting `openid`, `profile`, `email` and `offline_access`. | Authentication is delegated to the Premier League identity service; it is not a password API for third parties. |
| Can the toolkit reuse FPL's client with its own callback? | The authorization endpoint returned `Redirect URI mismatch` for `https://thatsivore.github.io/draft_toolkit/`, while the official FPL callback entered the normal sign-in flow. | A GitHub Pages callback is not registered and cannot complete the flow. |
| How does the official app read the editable team? | The published app calls `GET /api/my-team/{entry}/` and attaches a bearer credential to same-origin `/api/` requests. | The endpoint is private account state, not another public entry endpoint. |
| Does the current-team endpoint work anonymously? | An unauthenticated request returned HTTP 403 with `Authentication credentials were not provided.` | The existing public-entry URL cannot reveal current pre-deadline state. |
| Can GitHub Pages call the endpoint directly? | A preflight from the toolkit origin was rejected and did not receive an allowed CORS origin. | A token in frontend code would not solve the browser-origin restriction, and placing one there would be unsafe anyway. |
| Is credential sharing an acceptable workaround? | The [Premier League account-security guidance](https://www.premierleague.com/en/about/faq/account-security) warns that sharing FPL login credentials with third-party sites or apps puts the team at risk and says such team-management services are not endorsed. | Password collection, login proxying and copied sessions are explicitly outside the design boundary. |

The identity provider's public discovery document is available at [the official OpenID configuration endpoint](https://account.premierleague.com/as/.well-known/openid-configuration). Its existence documents the provider's capabilities; it is not evidence of an open third-party developer programme or authorization to use FPL data.

## Why the Seerr/Plex pattern does not transfer directly

Seerr can use Plex because Plex deliberately acts as an identity and authorization provider for connected applications. The connected service receives an account identity through an intended integration and can check a relevant server entitlement.

FPL currently exposes no equivalent toolkit client registration or consented account-to-entry integration. The FPL entry number is a public identifier, not an authentication secret or proof that the signed-in person owns the team. Hiding it from the address bar would not establish authorization.

## Supported architecture if Premier League approval is obtained

A future hosted connection should use a backend-for-frontend rather than placing account credentials in the static dashboard:

1. the toolkit creates its own server-side user session;
2. the user chooses **Connect FPL** and is redirected to the official Premier League authorization endpoint;
3. the Premier League redirects only to the toolkit's registered callback;
4. the backend completes PKCE and keeps any granted credentials encrypted and out of browser storage, URLs, logs and reports;
5. the backend fetches the minimum read-only team state and immediately normalizes it to the toolkit's private squad contract; and
6. every report request is authorized against the toolkit account that owns that connection.

This design is conditional on a sanctioned client registration, approved scopes/API use and the data rights needed for the intended personal or commercial use. It is not implementable merely by adding a login page to GitHub Pages.

## Bounded personal experiment

For personal use, the next technically useful experiment is a **user-initiated browser-local snapshot**, not a hosted FPL login integration.

The proposed boundary is:

- the user signs in only on the official FPL site;
- an explicit browser-local action requests the current team from that same FPL origin;
- the helper allowlists only squad picks, positions, captaincy, bank, selling/purchase prices, free-transfer state and chip availability;
- the helper removes entry and account identifiers before export;
- no password, authorization code, access/refresh token, cookie, email or profile data is read into the export or sent to the toolkit; and
- the resulting snapshot is accepted only by the local/private Standard FPL command and remains gitignored.

The strict, source-independent receiving contract is now implemented as [Standard FPL Private Snapshot Contract](STANDARD_FPL_PRIVATE_SNAPSHOT.md). It accepts only allowlisted team state and rejects extra identity or credential fields. The browser-local exporter remains a discovery candidate, not yet an approved implementation. It must first be proved that an already signed-in FPL page can produce the read-only response using its normal same-origin session without the helper extracting or replaying a bearer token. If that test fails, the browser-local connector stops; it must not escalate to copying local-storage credentials.

Even if technically successful, a browser extension or local helper adds installation and trust friction. It may be reasonable for the owner's personal use but is not a satisfactory paid onboarding path without Premier League approval and a clear distribution/security review.

## Next proof and stop conditions

The next proof requires the owner to sign in manually in the controlled browser on the official Premier League page. The test should inspect only status and sanitized field names from a same-origin, cookie/session-bound read. It must not print, copy or persist credentials.

| Result | Next action |
|---|---|
| Same-origin session-only read succeeds | Map the sanitized response into the implemented versioned allowlist, build a minimal local exporter and validate it against the existing Standard FPL POC. |
| The read requires helper access to a bearer token | Stop the connector experiment; retain public locked picks plus manual private inputs until a sanctioned integration exists. |
| The response lacks required finance/transfer/chip fields | Keep Phase 1 lineup advice, but do not build legal transfer recommendations from incomplete state. |
| Premier League offers an approved integration path | Replace the local experiment with the registered backend-for-frontend architecture. |

No automated FPL actions are in scope. The toolkit remains read-only decision support.
