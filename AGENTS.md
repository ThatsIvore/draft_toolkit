# Repository instructions

Read `docs/MAINTAINER_ONBOARDING.md` before changing collection, scoring, recommendations, public report data, privacy, workflows, or dashboard behavior.

## Working rules

- Start from the latest `origin/main`. For an existing pull request, compare its merge base and head with current `main`; refresh and rerun affected tests when later commits touch the same data flow.
- Preserve current ownership, locked scoring-Gameweek lineups, and next-actionable-Gameweek recommendations as separate facts.
- Keep Draft H2H and private Standard FPL state isolated. Standard reports must never use the public publish path.
- Preserve public redaction. Do not add real manager names, internal entry identifiers, credentials, private snapshots, or raw API payloads to public output or version control.
- Keep the toolkit advisory. Do not submit lineups, waivers, trades, transfers, captaincy, or chips.
- Diagnose without editing unless the request includes implementation. Publish changes through an unmerged pull request and merge only after explicit approval for that PR.

## Verification

Run focused tests first and then:

```bash
pytest -q
git diff --check
```

Run `node --check` for changed JavaScript. Visually inspect meaningful frontend changes at desktop and mobile sizes. Collector or schema changes require a successful post-merge collection and live-data verification in addition to a Pages deployment.
