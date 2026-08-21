from __future__ import annotations

from pathlib import Path
from typing import Any

from .api import DraftApiClient, FPLApiError, FantasyApiClient
from .config import Settings
from .diff import diff_ownership
from .fixtures import attach_fixture_matrix, build_team_fixture_matrix, planning_gameweeks
from .intelligence import attach_intelligence
from .lineup import fallback_lineup, normalize_lineup
from .normalize import choose_league_id, normalize_ownership
from .report import build_report
from .state import compact_ownership_state, decorate_change_manager_names
from .storage import newest_snapshot, read_json, timestamp_slug, write_json
from .waivers import attach_replacement_analysis


def collect(settings: Settings, client: DraftApiClient | None = None, fantasy_client: FantasyApiClient | None = None) -> dict[str, Any]:
    client = client or DraftApiClient()
    fantasy_client = fantasy_client or FantasyApiClient()
    root = Path(settings.output_dir)
    raw_dir = root / "raw"
    snapshot_dir = root / "snapshots"
    report_dir = root / "reports"
    state_path = root / "state" / "ownership.json"
    stamp = timestamp_slug()

    entry = client.entry_public(settings.draft_entry_id)
    bootstrap = client.bootstrap_static()
    fixtures = fantasy_client.fixtures()
    league_id = choose_league_id(entry, settings.draft_league_id)
    league = client.league_details(league_id)
    element_status = client.element_status(league_id)

    write_json(raw_dir / f"entry-{stamp}.json", entry)
    write_json(raw_dir / f"bootstrap-{stamp}.json", bootstrap)
    write_json(raw_dir / f"fixtures-{stamp}.json", fixtures)
    write_json(raw_dir / f"league-{stamp}.json", league)
    write_json(raw_dir / f"element-status-{stamp}.json", element_status)

    if state_path.exists():
        previous = read_json(state_path)
    else:
        previous_path = newest_snapshot(snapshot_dir)
        previous = read_json(previous_path) if previous_path else []

    ownership = normalize_ownership(element_status, league, bootstrap)
    planning_gws = planning_gameweeks(bootstrap, settings.planning_horizon, fixtures)
    fixture_matrix = build_team_fixture_matrix(fixtures, bootstrap, settings.planning_horizon)
    ownership = attach_fixture_matrix(ownership, fixture_matrix)
    ownership = attach_intelligence(
        ownership,
        previous=previous,
        my_entry_id=settings.draft_entry_id,
    )

    changes = diff_ownership(previous, ownership) if previous else []
    changes = decorate_change_manager_names(changes, league)

    snapshot_path = snapshot_dir / f"ownership-{stamp}.json"
    write_json(snapshot_path, ownership)
    write_json(state_path, compact_ownership_state(ownership))

    report = build_report(settings.draft_entry_id, league_id, league, bootstrap, ownership, changes, settings.planning_horizon, planning_gws)
    report["available_players"] = attach_replacement_analysis(
        report.get("available_players", []), report.get("my_squad", [])
    )
    report["planning_gameweeks"] = planning_gws
    report["snapshot"] = str(snapshot_path)
    report["intelligence_model"] = {
        "version": "v0.4",
        "description": "Action-oriented injury/stash scoring plus same-position waiver replacement deltas against the user's actual roster.",
    }

    lineup_gw = planning_gws[0] if planning_gws else 1
    lineup = None
    try:
        lineup_payload = client.entry_event(settings.draft_entry_id, lineup_gw)
        write_json(raw_dir / f"lineup-gw{lineup_gw}-{stamp}.json", lineup_payload)
        lineup = normalize_lineup(lineup_payload, report.get("my_squad", []), lineup_gw)
    except FPLApiError:
        lineup = None
    report["lineup"] = lineup or fallback_lineup(report.get("my_squad", []), lineup_gw)

    write_json(report_dir / "latest.json", report)
    return report
