#!/usr/bin/env python3
"""
Updates plugin information from GitHub releases and manifests.
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Optional, Tuple, List

import requests

# Configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}
REPO_FILE = "repo.json"
README_FILE = "README.md"
BADGE_FILE = "badge.json"
START_MARKER = "<!--START_MARKER-->"
END_MARKER = "<!--END_MARKER-->"
REQUEST_TIMEOUT = 10  # seconds
RATE_LIMIT_DELAY = 1  # seconds between API calls
KAMORI_COUNTS_URL = "https://kamori.goats.dev/Plugin/DownloadCounts"


def fetch_kamori_counts() -> dict:
    """Fetch official Dalamud installer download counts from kamori.goats.dev."""
    try:
        response = requests.get(KAMORI_COUNTS_URL, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            print("  Fetched kamori download counts.")
            return response.json()
    except Exception as e:
        print(f"  Warning: could not fetch kamori counts: {e}")
    return {}


def get_owner_repo(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract owner and repo name from GitHub URL."""
    if not url:
        return None, None
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url.strip("/"))
    return match.groups() if match else (None, None)


def to_unix_timestamp(iso_str: str) -> Optional[int]:
    """Convert ISO datetime string to Unix timestamp."""
    if not iso_str:
        return None
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        return int(dt.timestamp())
    except Exception:
        return None


def verify_and_fix_url(url: str, preferred_branch: str) -> str:
    """Verify URL is accessible and fix branch if needed."""
    if not url:
        return url

    try:
        if requests.head(url, timeout=REQUEST_TIMEOUT).status_code == 200:
            return url
    except Exception:
        pass

    # Try alternative branch
    new_url = url
    if preferred_branch == "master" and "/main/" in url:
        new_url = url.replace("/main/", "/master/")
    elif preferred_branch == "main" and "/master/" in url:
        new_url = url.replace("/master/", "/main/")

    if new_url != url:
        try:
            if requests.head(new_url, timeout=REQUEST_TIMEOUT).status_code == 200:
                return new_url
        except Exception:
            pass

    return url


def update_readme(plugins_list: list) -> bool:
    """Update the README.md file with plugin table."""
    if not os.path.exists(README_FILE):
        print("README.md not found, skipping table update.")
        return False

    lines = [
        "| Plugin Name | Description | Source |",
        "| :--- | :--- | :---: |"
    ]

    for plugin in plugins_list:
        name = plugin.get("Name", "Unknown")
        desc = plugin.get("Description", "")
        punch = plugin.get("Punchline", "")
        url = plugin.get("RepoUrl", "")

        full_desc = f"**{punch}**<br>{desc}" if punch else desc
        full_desc = full_desc.replace("\n", " ").replace("|", "-")

        lines.append(f"| **{name}** | {full_desc} | [Repo]({url}) |")

    table_content = "\n".join(lines)

    with open(README_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    start_idx = content.find(START_MARKER)
    end_idx = content.find(END_MARKER)

    if start_idx == -1 or end_idx == -1:
        print("Markers not found in README.md.")
        return False

    new_content = (
        f"{content[:start_idx + len(START_MARKER)]}\n"
        f"{table_content}\n"
        f"{content[end_idx:]}"
    )

    if new_content != content:
        with open(README_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("README.md updated.")
        return True

    return False


def format_count(count: int) -> str:
    """Format a download count for badge display (e.g. 19729 -> 19.7k)."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)


def update_badge(plugins_list: list) -> bool:
    """Write a shields.io endpoint JSON with the total download count."""
    total = sum(p.get("DownloadCount", 0) for p in plugins_list)
    badge = {
        "schemaVersion": 1,
        "label": "total downloads",
        "message": format_count(total),
        "color": "7aa2f7",
        "labelColor": "1a1b26"
    }
    content = json.dumps(badge, indent=2) + "\n"

    if os.path.exists(BADGE_FILE):
        with open(BADGE_FILE, "r", encoding="utf-8") as f:
            if f.read() == content:
                return False

    with open(BADGE_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print("badge.json updated.")
    return True


def fetch_manifest(owner: str, repo: str, internal_name: str) -> Tuple[Optional[dict], str]:
    """Fetch plugin manifest from GitHub."""
    manifest_candidates = [
        (f"https://raw.githubusercontent.com/{owner}/{repo}/master/{internal_name}.json", "master"),
        (f"https://raw.githubusercontent.com/{owner}/{repo}/main/{internal_name}.json", "main"),
        (f"https://raw.githubusercontent.com/{owner}/{repo}/master/{internal_name}/{internal_name}.json", "master"),
        (f"https://raw.githubusercontent.com/{owner}/{repo}/main/{internal_name}/{internal_name}.json", "main")
    ]

    for url, branch in manifest_candidates:
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                print(f"  Found manifest for {internal_name}")
                return response.json(), branch
        except Exception:
            continue

    return None, "master"


def update_plugin_from_manifest(plugin: dict, manifest_data: dict, branch: str) -> bool:
    """Update plugin data from manifest."""
    updated = False

    # Update text fields
    for field in ["Punchline", "Description", "Tags", "Name"]:
        val = manifest_data.get(field)
        if val and val != plugin.get(field):
            plugin[field] = val
            updated = True

    # Update IconUrl with verification
    if manifest_data.get("IconUrl"):
        fixed = verify_and_fix_url(manifest_data["IconUrl"], branch)
        if fixed != plugin.get("IconUrl"):
            plugin["IconUrl"] = fixed
            updated = True

    # Update ImageUrls with verification
    raw_imgs = manifest_data.get("ImageUrls", [])
    fixed_imgs = [verify_and_fix_url(img, branch) for img in raw_imgs]
    if fixed_imgs != plugin.get("ImageUrls"):
        plugin["ImageUrls"] = fixed_imgs
        updated = True

    return updated


def update_plugin_releases(plugin: dict, owner: str, repo: str) -> tuple[bool, str | None]:
    """Update plugin version and download information from latest release."""
    internal_name = plugin.get("InternalName", "unknown")

    # Fetch latest release
    latest_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        response = requests.get(latest_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            release = response.json()
            version = release.get("tag_name", "").lstrip("v")
            if re.match(r"^\d+\.\d+\.\d+$", version):
                version = f"{version}.0"
            download_link = next(
                (asset["browser_download_url"]
                 for asset in release.get("assets", [])
                 if asset["name"].endswith(".zip")),
                None
            )

            if version and download_link and plugin.get("AssemblyVersion") != version:
                print(f"  New version {version} for {internal_name}")
                plugin["AssemblyVersion"] = version
                plugin["DownloadLinkInstall"] = download_link
                plugin["DownloadLinkUpdate"] = download_link
                plugin["DownloadLinkTesting"] = download_link
                plugin["Changelog"] = release.get("body", "")
                return True, f"{internal_name} to v{version}"
    except Exception as e:
        print(f"  Error fetching latest release for {internal_name}: {e}")

    return False, None


def update_plugin_stats(plugin: dict, owner: str, repo: str, kamori_counts: dict) -> bool:
    """Update plugin download count and last update time."""
    updated = False
    internal_name = plugin.get("InternalName", "unknown")

    # Fetch all releases for stats
    all_releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=100"
    try:
        response = requests.get(all_releases_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            all_releases = response.json()

            # Calculate total downloads
            total_downloads = sum(
                asset.get("download_count", 0)
                for release in all_releases
                for asset in release.get("assets", [])
                if asset.get("name", "").endswith(".zip")
            )
            total_downloads += kamori_counts.get(internal_name, 0)

            if plugin.get("DownloadCount") != total_downloads:
                plugin["DownloadCount"] = total_downloads
                updated = True

            # Find last update time
            all_dates = [
                release.get("published_at") or release.get("created_at")
                for release in all_releases
                if release.get("published_at") or release.get("created_at")
            ]

            if all_dates:
                last_updated_iso = max(all_dates)
                last_updated_unix = to_unix_timestamp(last_updated_iso)

                if last_updated_unix and plugin.get("LastUpdate") != last_updated_unix:
                    plugin["LastUpdate"] = last_updated_unix
                    updated = True
    except Exception as e:
        print(f"  Error fetching stats for {internal_name}: {e}")

    return updated


def main():
    """Main function to update all plugins."""
    # Load existing plugins
    with open(REPO_FILE, "r", encoding="utf-8") as f:
        plugins = json.load(f)

    updated = False
    version_updates: list[str] = []
    stats_changed = False
    kamori_counts = fetch_kamori_counts()

    for i, plugin in enumerate(plugins):
        repo_url = plugin.get("RepoUrl")
        internal_name = plugin.get("InternalName")

        if not repo_url or not internal_name:
            continue

        print(f"\nProcessing {internal_name} ({i+1}/{len(plugins)})...")

        owner, repo = get_owner_repo(repo_url)
        if not owner or not repo:
            print(f"  Could not parse repo URL: {repo_url}")
            continue

        # Fetch and update from manifest
        manifest_data, detected_branch = fetch_manifest(owner, repo, internal_name)
        if manifest_data:
            if update_plugin_from_manifest(plugin, manifest_data, detected_branch):
                updated = True

        # Update release information
        release_updated, version_str = update_plugin_releases(plugin, owner, repo)
        if release_updated:
            updated = True
            if version_str:
                version_updates.append(version_str)

        # Update statistics
        if update_plugin_stats(plugin, owner, repo, kamori_counts):
            updated = True
            stats_changed = True

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)

    # Save updated plugins
    if updated:
        print("\nUpdating repo.json...")
        with open(REPO_FILE, "w", encoding="utf-8") as f:
            json.dump(plugins, f, indent=2, ensure_ascii=False)

    # Update README and total downloads badge
    readme_changed = update_readme(plugins)
    badge_changed = update_badge(plugins)

    if not updated and not readme_changed and not badge_changed:
        print("\nNo changes needed.")
        return 0

    if version_updates:
        if len(version_updates) == 1:
            msg = f"Update {version_updates[0]}"
        else:
            names = ", ".join(v.split(" to ")[0] for v in version_updates)
            msg = f"Update {names} to new versions"
    elif stats_changed:
        msg = "Update plugin download counts and stats"
    elif readme_changed:
        msg = "Update README plugin table"
    else:
        msg = "Update total downloads badge"

    if readme_changed and "README" not in msg:
        msg += " and README"

    with open(".commit_message.txt", "w", encoding="utf-8") as f:
        f.write(msg)

    print(f"\nCommit message: {msg}")
    print("\nUpdate complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
