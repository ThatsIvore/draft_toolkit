"""Reviewed provider ratings: descriptive evidence, never a scoring multiplier."""
from datetime import datetime, timezone
from importlib.resources import files
import json
import math
from urllib.parse import urlparse

HOSTS = {"fotmob": "www.fotmob.com", "sofascore": "www.sofascore.com", "flashscore": "www.flashscore.com"}


def reviewed_ratings(bootstrap, completed, *, rows=None, now=None):
    now = now or datetime.now(timezone.utc)
    if rows is None:
        rows = json.loads(files("fpl_toolkit").joinpath("data/reviewed-ratings.json").read_text())
    events = bootstrap.get("events", [])
    if isinstance(events, dict):
        events = events.get("data", [])
    season = str(next((e.get("deadline_time", "") for e in events if e.get("id") == 1), ""))[:4]
    ids = {int(e["code"]): int(e["id"]) for e in bootstrap.get("elements", []) if e.get("code") is not None}
    accepted, rejected = {}, 0
    for row in rows:
        try:
            provider = row["provider"]
            url = urlparse(row["source_url"])
            observed = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
            age = (now - observed).total_seconds()
            rating = float(row["rating"])
            code = int(row["code"])
            apps, minutes = (int(row[k]) for k in ("appearances", "minutes"))
            starts = None if row.get("starts") is None else int(row["starts"])
            valid = (url.scheme == "https" and url.netloc == HOSTS[provider]
                     and str(row["season"]) == season and row["competition"] == "Premier League"
                     and completed and row["through_gameweek"] == max(completed)
                     and 0 <= age <= 48 * 3600 and math.isfinite(rating) and 0 <= rating <= 10
                     and (starts is None or 0 <= starts <= apps) and apps > 0 and 0 < minutes <= apps * 130
                     and code in ids)
            if not valid:
                raise ValueError("Ineligible evidence")
            public = {k: row[k] for k in ("provider", "source_url", "observed_at", "through_gameweek", "season", "competition")}
            public.update(rating=rating, appearances=apps, starts=starts, minutes=minutes,
                          small_sample=apps < 5 or minutes < 450, recommendations_affected=False)
            key = (ids[code], provider)
            if key not in accepted or public["observed_at"] > accepted[key]["observed_at"]:
                accepted[key] = public
        except (KeyError, TypeError, ValueError, OverflowError):
            rejected += 1
    result = {}
    for (player_id, _), evidence in sorted(accepted.items()):
        result.setdefault(player_id, []).append(evidence)
    return result, {"mode": "reviewed_shadow", "status": "available" if result else "unavailable",
                    "players": len(result), "rejected_records": rejected, "recommendations_affected": False}
