# Dalamud Plugin CI/CD Workflow Guide

How to add the standardized CI/CD workflows to a new or existing Dalamud plugin repo.

## Prerequisites

- A `PAT_TOKEN` repository secret with `repo` scope (for cross-repo dispatch and tag pushing)
- A `packages.lock.json` in your project (run `dotnet restore --use-lock-file` to generate one)
- Your plugin must already have an entry in `DalamudPluginRepo/repo.json`

## Files to Create/Modify

You need 5 workflow files + dependabot config. Replace `PLUGIN_NAME` with your plugin's `InternalName` (e.g. `SpotifyHonorific`, `FoxyJumpscare`).

### Choose your runner

- **Ubuntu** (`ubuntu-latest`): Default choice. Faster startup, cheaper. Works for most plugins.
- **Windows** (`windows-latest`): Only if your plugin has Windows-native dependencies (e.g. NAudio).

---

### 1. `.github/workflows/setup-and-build.yml` (Create)

Reusable workflow that both `build.yml` and `release.yml` call.

#### Ubuntu version

```yaml
name: Setup and Build

on:
  workflow_call:
    inputs:
      configuration:
        type: string
        default: "Release"
      version:
        type: string
        default: ""
    secrets:
      token:
        required: false

jobs:
  build:
    runs-on: ubuntu-latest
    env:
      DALAMUD_HOME: /tmp/dalamud
      DALAMUD_ARCHIVE_URL: ${{ vars.DALAMUD_ARCHIVE_URL || 'https://goatcorp.github.io/dalamud-distrib/latest.zip' }}
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v6
        with:
          token: ${{ secrets.token || github.token }}
          fetch-depth: 0

      - name: Set up .NET
        uses: actions/setup-dotnet@v5
        with:
          dotnet-version: 10.0.x
          cache: true
          cache-dependency-path: '**/packages.lock.json'

      - name: Cache Dalamud
        uses: actions/cache@v5
        id: cache-dalamud
        with:
          path: ${{ env.DALAMUD_HOME }}
          key: dalamud-${{ env.DALAMUD_ARCHIVE_URL }}

      - name: Download Dalamud Latest
        if: steps.cache-dalamud.outputs.cache-hit != 'true'
        run: |
          wget ${{ env.DALAMUD_ARCHIVE_URL }} -O ${{ env.DALAMUD_HOME }}.zip
          unzip ${{ env.DALAMUD_HOME }}.zip -d ${{ env.DALAMUD_HOME }}

      - name: Build Project
        run: |
          BUILD_ARGS="--configuration ${{ inputs.configuration }} PLUGIN_NAME/PLUGIN_NAME.csproj"
          if [ -n "${{ inputs.version }}" ]; then
            BUILD_ARGS="$BUILD_ARGS -p:AssemblyVersion=${{ inputs.version }}"
          fi
          dotnet build $BUILD_ARGS

      - name: Upload Build Artifact
        uses: actions/upload-artifact@v6
        with:
          name: PLUGIN_NAME
          retention-days: 14
          path: |
            PLUGIN_NAME/bin/${{ inputs.configuration }}/*
            !PLUGIN_NAME/bin/${{ inputs.configuration }}/PLUGIN_NAME/

      - name: Rename Release Asset
        if: inputs.version != ''
        run: mv PLUGIN_NAME/bin/${{ inputs.configuration }}/PLUGIN_NAME/latest.zip PLUGIN_NAME/bin/${{ inputs.configuration }}/PLUGIN_NAME/PLUGIN_NAME.zip

      - name: Upload Release Asset
        if: inputs.version != ''
        uses: actions/upload-artifact@v6
        with:
          name: PLUGIN_NAME-release
          retention-days: 1
          path: PLUGIN_NAME/bin/${{ inputs.configuration }}/PLUGIN_NAME/PLUGIN_NAME.zip
```

#### Windows version

Only differences from Ubuntu:
- `runs-on: windows-latest`
- `DALAMUD_HOME: ${{ github.workspace }}\dalamud`
- Download step uses `shell: pwsh` with `Invoke-WebRequest`/`Expand-Archive`
- Build step uses `shell: pwsh` with PowerShell array splatting
- Rename step uses `shell: pwsh` with `Move-Item`

See `FoxyJumpscare/.github/workflows/setup-and-build.yml` for the full Windows version.

---

### 2. `.github/workflows/build.yml` (Create/Replace)

```yaml
name: Build

on:
  push:
    branches: [ "master", "main" ]
  pull_request:
    branches: [ "master", "main" ]

jobs:
  build:
    uses: ./.github/workflows/setup-and-build.yml
    with:
      configuration: Release
```

---

### 3. `.github/workflows/release.yml` (Create/Replace)

```yaml
name: Build and Release

on:
  push:
    tags:
      - "v*.*.*"
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to release (e.g. 1.0.0)'
        required: true
        default: '1.0.0'

permissions:
  contents: write

jobs:
  prepare:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.version.outputs.version }}
      tag_name: ${{ steps.version.outputs.tag_name }}
    steps:
      - name: Determine Version
        id: version
        run: |
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            echo "version=${{ github.event.inputs.version }}" >> $GITHUB_OUTPUT
            echo "tag_name=v${{ github.event.inputs.version }}" >> $GITHUB_OUTPUT
          else
            VERSION="${{ github.ref_name }}"
            echo "version=${VERSION#v}" >> $GITHUB_OUTPUT
            echo "tag_name=${{ github.ref_name }}" >> $GITHUB_OUTPUT
          fi

  build:
    needs: prepare
    uses: ./.github/workflows/setup-and-build.yml
    with:
      configuration: Release
      version: ${{ needs.prepare.outputs.version }}
    secrets:
      token: ${{ secrets.PAT_TOKEN }}

  release:
    needs: [ prepare, build ]
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Download Release Asset
        uses: actions/download-artifact@v6
        with:
          name: PLUGIN_NAME-release
          path: release

      - name: Generate Changelog
        run: |
          TAG="${{ needs.prepare.outputs.tag_name }}"
          PREV_TAG=$(git describe --tags --abbrev=0 "$TAG^" 2>/dev/null || true)
          if [ -z "$PREV_TAG" ]; then
            git log --pretty=format:"- %s" "$TAG" > changelog.txt 2>/dev/null || git log --pretty=format:"- %s" HEAD > changelog.txt
          else
            git log --pretty=format:"- %s" "$PREV_TAG..$TAG" > changelog.txt
          fi

      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          name: ${{ needs.prepare.outputs.tag_name }}
          tag_name: ${{ needs.prepare.outputs.tag_name }}
          draft: false
          prerelease: false
          body_path: changelog.txt
          files: release/PLUGIN_NAME.zip
        env:
          GITHUB_TOKEN: ${{ github.token }}

      - name: Dispatch Plugin Repo Update
        run: |
          curl -X POST \
            -H "Authorization: token ${{ secrets.PAT_TOKEN }}" \
            -H "Accept: application/vnd.github+json" \
            https://api.github.com/repos/Valiice/DalamudPluginRepo/dispatches \
            -d '{"event_type":"plugin-release","client_payload":{"plugin":"PLUGIN_NAME","version":"${{ needs.prepare.outputs.version }}","tag":"${{ needs.prepare.outputs.tag_name }}","repo":"${{ github.repository }}"}}'
```

---

### 4. `.github/workflows/scheduled-bump.yml` (Create)

Copy as-is from any existing plugin. No plugin-specific values to change.

```yaml
name: Daily Release Scheduler

on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  check-and-tag:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v6
        with:
          fetch-depth: 0
          token: ${{ secrets.PAT_TOKEN }}

      - name: Configure Git
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

      - name: Calculate Next Version
        id: version
        run: |
          LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
          echo "Latest tag found: $LATEST_TAG"

          LOG_RANGE="$LATEST_TAG..HEAD"
          if [ "$LATEST_TAG" = "v0.0.0" ]; then
              LOG_RANGE="HEAD"
          fi

          DEPENDABOT_UPDATES=$(
            git log $LOG_RANGE --pretty="%s" |
            grep -i "dependabot/" |
            grep -vi "dependabot/github_actions" |
            wc -l
          )

          echo "Found $DEPENDABOT_UPDATES code dependency updates."

          if [ "$DEPENDABOT_UPDATES" -eq 0 ]; then
            echo "No Dependabot code merges found (Manual commits & Action updates are ignored). Skipping release."
            echo "should_release=false" >> $GITHUB_OUTPUT
            exit 0
          fi

          echo "Found valid Dependabot code merge. Proceeding with patch release."

          VERSION=${LATEST_TAG#v}
          IFS='.' read -r major minor patch <<< "$VERSION"

          patch=${patch:-0}
          NEW_PATCH=$((patch + 1))

          NEW_TAG="v$major.$minor.$NEW_PATCH"

          echo "New Version: $NEW_TAG"
          echo "TAG_NAME=$NEW_TAG" >> $GITHUB_ENV
          echo "should_release=true" >> $GITHUB_OUTPUT

      - name: Push New Tag
        if: steps.version.outputs.should_release == 'true'
        run: |
          git tag ${{ env.TAG_NAME }}
          git push origin ${{ env.TAG_NAME }}
```

---

### 5. `.github/workflows/dependabot-auto-merge.yml` (Create)

Copy as-is. No plugin-specific values.

```yaml
name: Dependabot Auto-Merge

on: pull_request

permissions:
  contents: write
  pull-requests: write

jobs:
  dependabot:
    runs-on: ubuntu-latest
    if: github.actor == 'dependabot[bot]'
    steps:
      - name: Dependabot metadata
        id: metadata
        uses: dependabot/fetch-metadata@v2
        with:
          github-token: "${{ secrets.GITHUB_TOKEN }}"

      - name: Enable auto-merge for Patch updates ONLY
        if: steps.metadata.outputs.update-type == 'version-update:semver-patch'
        run: gh pr merge --auto --merge "$PR_URL"
        env:
          PR_URL: ${{github.event.pull_request.html_url}}
          GITHUB_TOKEN: ${{secrets.GITHUB_TOKEN}}
```

---

### 6. `.github/dependabot.yml` (Create)

```yaml
version: 2
updates:
  - package-ecosystem: "nuget"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

---

### 7. `.gitignore` (Update)

Make sure these are present:

```
.claude/
images/
```

---

## Checklist

- [ ] Replace every `PLUGIN_NAME` with your plugin's InternalName
- [ ] Check if you need Windows or Ubuntu runner for `setup-and-build.yml`
- [ ] Ensure `PAT_TOKEN` secret is set in the repo (Settings > Secrets and variables > Actions)
- [ ] Generate `packages.lock.json` if missing: `dotnet restore --use-lock-file`
- [ ] Ensure your plugin has an entry in `DalamudPluginRepo/repo.json`
- [ ] Push to master and verify `build.yml` passes
- [ ] Create a test tag to verify the full release pipeline

## Flow

```
Dependabot PR ──> auto-merge.yml (merge patch)
                        │
                        v
                  push to master ──> build.yml ──> setup-and-build.yml (CI)
                        │
                        v
               scheduled-bump.yml (daily 4AM UTC, detects merge, pushes tag)
                        │
                        v
                 tag push v*.*.* ──> release.yml
                                       ├── prepare (version)
                                       ├── build (setup-and-build.yml with version stamp)
                                       └── release (changelog + GitHub release + dispatch)
                                                                              │
                                                                              v
                                                    DalamudPluginRepo/update-repo.yml
                                                    (updates repo.json with new version)
```
