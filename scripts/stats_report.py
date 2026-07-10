#!/usr/bin/env python3
"""
Reports download growth and estimated active users per plugin from the
stats CSVs (stats/backfill.csv and stats/history.csv).

Usage (from the repository root):
    python scripts/stats_report.py            # all plugins
    python scripts/stats_report.py SpotifyHonorific
"""
import csv
import os
import sys
from datetime import datetime, timedelta, timezone

BACKFILL_FILE = "stats/backfill.csv"
HISTORY_FILE = "stats/history.csv"

# Releases published shortly after a Dalamud API level bump see a forced
# full re-download wave and must not be used for active-user estimates.
API_BUMP_WINDOW = timedelta(days=14)
# A release must have been current at least this long for its download
# count to approximate the active userbase.
MIN_DAYS_LIVE = 3


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc)


def load_backfill() -> dict:
    """plugin -> list of (ts, total, api_level), chronological."""
    series: dict = {}
    if not os.path.exists(BACKFILL_FILE):
        return series
    with open(BACKFILL_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            series.setdefault(row["plugin"], []).append(
                (parse_ts(row["timestamp"]), int(row["total_downloads"]), row["api_level"])
            )
    for points in series.values():
        points.sort(key=lambda p: p[0])
    return series


def load_history() -> dict:
    """plugin -> {"releases": {tag: {"published", "count"}}, "totals": [(ts, total)]}."""
    history: dict = {}
    if not os.path.exists(HISTORY_FILE):
        return history

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: r["timestamp"])

    running: dict = {}
    for row in rows:
        plugin = history.setdefault(
            row["plugin"], {"releases": {}, "totals": []}
        )
        tag, count = row["tag"], int(row["downloads"])
        plugin["releases"][tag] = {
            "published": parse_ts(row["published"]) if row["published"] else None,
            "count": count,
        }
        counts = running.setdefault(row["plugin"], {})
        counts[tag] = count
        plugin["totals"].append((parse_ts(row["timestamp"]), sum(counts.values())))
    return history


def api_bump_times(backfill_points: list) -> list:
    """Timestamps where the plugin's DalamudApiLevel changed."""
    bumps = []
    previous = None
    for ts, _, api_level in backfill_points:
        if previous is not None and api_level != previous:
            bumps.append(ts)
        previous = api_level
    return bumps


def rate_per_day(totals: list, days: int, now: datetime):
    """Average downloads/day over the trailing window, or None if not enough data."""
    if len(totals) < 2:
        return None
    cutoff = now - timedelta(days=days)
    window = [p for p in totals if p[0] >= cutoff]
    if len(window) < 2:
        return None
    (t0, v0), (t1, v1) = window[0], window[-1]
    span_days = (t1 - t0).total_seconds() / 86400
    if span_days < days * 0.5:  # window barely covered; not meaningful
        return None
    return (v1 - v0) / span_days


def report_plugin(name: str, backfill: dict, history: dict, now: datetime) -> None:
    points = backfill.get(name, [])
    hist = history.get(name, {"releases": {}, "totals": []})
    releases = [
        (tag, info) for tag, info in hist["releases"].items() if info["published"]
    ]
    releases.sort(key=lambda r: r[1]["published"])
    bumps = api_bump_times(points)

    total = points[-1][1] if points else sum(i["count"] for _, i in releases)
    print(f"\n=== {name} ===")
    print(f"Total downloads: {total}")

    # Growth rates from the merged cumulative series
    totals = [(ts, v) for ts, v, _ in points] + hist["totals"]
    totals.sort(key=lambda p: p[0])
    for days in (7, 30):
        rate = rate_per_day(totals, days, now)
        print(f"Downloads/day (last {days}d): " + (f"{rate:.1f}" if rate is not None else "n/a"))

    if not releases:
        print("No release history recorded yet.")
        return

    # Per-release table; a release is "live" until the next one is published
    print(f"\n{'release':12} {'published':12} {'days live':>9} {'downloads':>9} {'dls/day':>8}  note")
    active_estimate = None
    for i, (tag, info) in enumerate(releases):
        published = info["published"]
        end = releases[i + 1][1]["published"] if i + 1 < len(releases) else now
        days_live = max((end - published).total_seconds() / 86400, 0.01)
        bumped = any(bump - timedelta(days=3) <= published <= bump + API_BUMP_WINDOW for bump in bumps)
        superseded = i + 1 < len(releases)

        note = "api bump" if bumped else ""
        if not bumped and superseded and days_live >= MIN_DAYS_LIVE:
            active_estimate = (tag, info["count"], days_live)
        print(
            f"{tag:12} {published.date().isoformat():12} {days_live:9.1f} "
            f"{info['count']:9} {info['count'] / days_live:8.1f}  {note}"
        )

    if active_estimate:
        tag, count, days_live = active_estimate
        print(
            f"\nEstimated active users: ~{count} "
            f"(downloads of {tag} during its {days_live:.0f} days as the current release)"
        )
    else:
        print("\nEstimated active users: n/a (no suitable release: needs a superseded, "
              f"non-api-bump release live >= {MIN_DAYS_LIVE} days)")


def main() -> int:
    backfill = load_backfill()
    history = load_history()
    if not backfill and not history:
        print("No stats found. Run scripts/backfill_stats.py or wait for the "
              "update-plugins workflow to populate stats/history.csv.")
        return 1

    now = datetime.now(timezone.utc)
    names = sorted(
        set(backfill) | set(history),
        key=lambda n: backfill.get(n, [(None, 0, None)])[-1][1],
        reverse=True,
    )
    if len(sys.argv) > 1:
        wanted = sys.argv[1].lower()
        names = [n for n in names if n.lower() == wanted]
        if not names:
            print(f"Unknown plugin: {sys.argv[1]}")
            return 1

    for name in names:
        report_plugin(name, backfill, history, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
