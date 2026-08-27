from __future__ import annotations

from pathlib import Path
from typing import Any

from .api import DraftApiClient, FPLApiError, FantasyApiClient
from .baseline import baseline_lookup, capture_performance_baseline
from .changefeed import build_change_feed, capture_decision_state
from .config import Settings
from .diff import diff_ownership
from .fixtures import attach_fixture_matrix, build_team_fixture_matrix, planning_gameweeks
from .h2h import build_h2h_matchup, build_h2h_outlook
from .injury_stash import build_injury_stash_dashboard
from .intelligence import attach_intelligence
from .lineup import fallback_lineup, normalize_lineup
from .normalize import choose_league_id, normalize_ownership
from .opponent_profile import build_manager_profiles, lineup_decision, update_manager_history
from .outcomes import build_outcome_diagnostics, gameweek_phase
from .optimizer import recommend_lineup
from .planner import build_schedule_planner
from .report import build_report, current_gameweek
from .recent_match_evidence import build_recent_match_evidence, fetch_completed_event_live
from .state import compact_ownership_state, decorate_change_manager_names
from .storage import newest_snapshot, read_json, timestamp_slug, write_json
from .transfer_intel import attach_transfer_intel
from .waivers import attach_replacement_analysis


def _final_lineup_decisions(
    client: DraftApiClient,
    league: dict[str, Any],
    ownership: list[dict[str, Any]],
    gameweek: int,
    phase: str,
) -> dict[str, dict[str, Any]]:
    if phase != "FINAL":
        return {}
    decisions: dict[str, dict[str, Any]] = {}
    entries = league.get("league_entries") or league.get("entries") or []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("entry_id", entry.get("entry"))
        if entry_id is None:
            continue
        try:
            payload = client.entry_event(str(entry_id), gameweek)
            decision = lineup_decision(normalize_lineup(payload, ownership, gameweek))
        except FPLApiError:
            decision = None
        if decision:
            decisions[str(entry_id)] = decision
    return decisions


def collect(settings: Settings, client: DraftApiClient | None = None, fantasy_client: FantasyApiClient | None = None) -> dict[str, Any]:
    client = client or DraftApiClient()
    fantasy_client = fantasy_client or FantasyApiClient()
    root = Path(settings.output_dir)
    raw_dir = root / "raw"
    snapshot_dir = root / "snapshots"
    report_dir = root / "reports"
    state_path = root / "state" / "ownership.json"
    decision_state_path = root / "state" / "decision.json"
    manager_history_path = root / "state" / "manager-decisions.json"
    public_report_path = Path("public/data/latest.json")
    baseline_path = root / "state" / "performance-baseline.json"
    draft_path = root / "draft" / "league-draft.json"
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
    if decision_state_path.exists():
        previous_decision_state = read_json(decision_state_path)
    elif public_report_path.exists():
        previous_decision_state = capture_decision_state(read_json(public_report_path))
    else:
        previous_decision_state = None
    manager_history = read_json(manager_history_path) if manager_history_path.exists() else None
    draft = read_json(draft_path) if draft_path.exists() else None

    ownership = normalize_ownership(element_status, league, bootstrap)
    planning_gws = planning_gameweeks(bootstrap, settings.planning_horizon, fixtures)
    season_gw = current_gameweek(bootstrap, planning_gws)
    decision_gw = planning_gws[0] if planning_gws else (1 if season_gw in (None, 0) else int(season_gw) + 1)
    scoring_gw = decision_gw if season_gw in (None, 0) else int(season_gw)
    fixture_matrix = build_team_fixture_matrix(
        fixtures,
        bootstrap,
        settings.planning_horizon,
        gameweeks=planning_gws,
    )
    ownership = attach_fixture_matrix(ownership, fixture_matrix)
    ownership = attach_transfer_intel(ownership, fixture_matrix)
    scoring_fixture_matrix = build_team_fixture_matrix(
        fixtures,
        bootstrap,
        1,
        gameweeks=[scoring_gw],
    )
    ownership = attach_fixture_matrix(ownership, scoring_fixture_matrix, field="_scoring_fixtures")

    recent_payloads, recent_status = fetch_completed_event_live(fantasy_client, bootstrap)
    recent_evidence = build_recent_match_evidence(ownership, recent_payloads)

    if baseline_path.exists():
        performance_baseline_rows = read_json(baseline_path)
    elif season_gw in (None, 0):
        performance_baseline_rows = capture_performance_baseline(ownership)
        write_json(baseline_path, performance_baseline_rows)
    else:
        performance_baseline_rows = []

    ownership = attach_intelligence(
        ownership,
        previous=previous,
        my_entry_id=settings.draft_entry_id,
        performance_baseline=baseline_lookup(performance_baseline_rows),
        current_gameweek=season_gw,
        recent_match_evidence=recent_evidence,
    )
    ownership = [
        {key: value for key, value in player.items() if key != "_scoring_fixtures"}
        for player in ownership
    ]

    changes = diff_ownership(previous, ownership) if previous else []
    changes = decorate_change_manager_names(changes, league)

    snapshot_path = snapshot_dir / f"ownership-{stamp}.json"
    write_json(snapshot_path, ownership)
    write_json(state_path, compact_ownership_state(ownership))

    report = build_report(settings.draft_entry_id, league_id, league, bootstrap, ownership, changes, settings.planning_horizon, planning_gws)
    report["available_players"] = attach_replacement_analysis(
        report.get("available_players", []),
        report.get("my_squad", []),
        current_gameweek=decision_gw,
    )
    report["injury_stash"] = build_injury_stash_dashboard(
        report.get("my_squad", []),
        report.get("available_players", []),
        tracked_players=ownership,
    )
    report["planning_gameweeks"] = planning_gws
    report["decision_gameweek"] = decision_gw
    report["schedule_planner"] = build_schedule_planner(
        report.get("my_squad", []),
        report.get("available_players", []),
        planning_gws,
    )
    report["snapshot"] = str(snapshot_path)
    report["intelligence_model"] = {
        "version": "v0.6.0",
        "description": "Early-season calibrated model with durable performance and role priors, capped position-relative grades from final official Gameweeks, live-match stabilization, floor/upside and conservative waiver guardrails.",
        "performance_baseline_players": len(performance_baseline_rows),
        "recent_match_evidence": {
            "version": "v1",
            "status": recent_status,
            "completed_gameweeks": [gameweek for gameweek, _ in recent_payloads],
        },
    }

    scoring_phase = gameweek_phase(fixtures, scoring_gw)
    decision_phase = gameweek_phase(fixtures, decision_gw)
    lineup_decisions = _final_lineup_decisions(client, league, ownership, scoring_gw, scoring_phase)
    manager_history = update_manager_history(
        manager_history,
        league,
        ownership,
        changes,
        captured_at=report.get("generated_at"),
        gameweek=decision_gw,
        lineup_decisions=lineup_decisions,
    )
    write_json(manager_history_path, manager_history)
    manager_profiles = build_manager_profiles(league, ownership, draft, manager_history)
    report["gameweek_phase"] = scoring_phase
    report["decision_gameweek_phase"] = decision_phase
    report["recommended_lineup"] = recommend_lineup(report.get("my_squad", []), decision_gw)
    report["h2h_matchup"] = build_h2h_matchup(
        league,
        settings.draft_entry_id,
        report.get("my_squad", []),
        ownership,
        report.get("available_players", []),
        decision_gw,
        my_lineup=report["recommended_lineup"],
        phase=decision_phase,
        manager_profiles=manager_profiles,
    )

    lineup = None
    try:
        lineup_payload = client.entry_event(settings.draft_entry_id, scoring_gw)
        write_json(raw_dir / f"lineup-gw{scoring_gw}-{stamp}.json", lineup_payload)
        # A locked scoring-Gameweek lineup may contain a player who has since
        # left the current squad through waivers. Resolve those historical picks
        # against the complete player pool rather than today's ownership only.
        lineup = normalize_lineup(lineup_payload, ownership, scoring_gw)
    except FPLApiError:
        lineup = None
    report["lineup"] = lineup or fallback_lineup(report.get("my_squad", []), scoring_gw)

    outcome_report = dict(report)
    if scoring_gw != decision_gw:
        scoring_recommendation = recommend_lineup(report.get("my_squad", []), scoring_gw)
        outcome_report["recommended_lineup"] = scoring_recommendation
        outcome_report["h2h_matchup"] = build_h2h_matchup(
            league,
            settings.draft_entry_id,
            report.get("my_squad", []),
            ownership,
            report.get("available_players", []),
            scoring_gw,
            my_lineup=scoring_recommendation,
            phase=scoring_phase,
            manager_profiles=manager_profiles,
        )
    report["outcome_diagnostics"] = build_outcome_diagnostics(
        previous_decision_state,
        outcome_report,
        scoring_phase,
        scoring_gw,
    )
    report["h2h_outlook"] = build_h2h_outlook(
        league,
        settings.draft_entry_id,
        report.get("my_squad", []),
        ownership,
        planning_gws,
        frozen_current=(report.get("outcome_diagnostics") or {}).get("current"),
        manager_profiles=manager_profiles,
        scoring_gameweek=scoring_gw,
    )
    report["change_feed"] = build_change_feed(previous_decision_state, report, changes)
    write_json(decision_state_path, capture_decision_state(report))

    write_json(report_dir / "latest.json", report)
    return report
