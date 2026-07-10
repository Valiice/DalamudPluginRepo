#!/usr/bin/env python3
"""
One-time backfill: reconstructs cumulative plugin download counts from the
git history of repo.json and writes them to stats/backfill.csv.

Run from the repository root. Safe to re-run (overwrites the output file).
"""
import csv
import json
import os
import subprocess
import sys

REPO_FILE = "repo.json"
OUT_FILE = "stats/backfill.csv"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def main() -> int:
    log = git("log", "--reverse", "--format=%H %cI", "--", REPO_FILE)
    commits = [line.split(" ", 1) for line in log.splitlines() if " " in line]
    print(f"Scanning {len(commits)} commits touching {REPO_FILE}...")

    last_seen: dict = {}
    rows: list = []
    for sha, timestamp in commits:
        try:
            plugins = json.loads(git("show", f"{sha}:{REPO_FILE}"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        if not isinstance(plugins, list):
            continue

        for plugin in plugins:
            name = plugin.get("InternalName")
            count = plugin.get("DownloadCount")
            if not name or count is None:
                continue
            value = (count, plugin.get("AssemblyVersion", ""), plugin.get("DalamudApiLevel", ""))
            if last_seen.get(name) != value:
                rows.append((timestamp, name, *value))
                last_seen[name] = value

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "plugin", "total_downloads", "version", "api_level"])
        writer.writerows(rows)

    print(f"{OUT_FILE}: wrote {len(rows)} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
