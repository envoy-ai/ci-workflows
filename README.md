# ci-workflows

Shared reusable GitHub Actions workflows for EnvoyAI repositories.

## Workflows

### `reusable-release-please.yml`

Wraps [googleapis/release-please-action](https://github.com/googleapis/release-please-action) for automated version management, changelogs, and GitHub Releases.

**Inputs:**

- `release-type` (required): `python` or `node`
- `config-file` (optional): path to `release-please-config.json` (default: repo root)
- `manifest-file` (optional): path to `.release-please-manifest.json` (default: repo root)

**Outputs:**

- `release_created`: boolean
- `tag_name`: e.g., `v1.2.0`
- `version`: e.g., `1.2.0`

**Usage:**

```yaml
jobs:
  release:
    uses: envoy-ai/ci-workflows/.github/workflows/reusable-release-please.yml@main
    with:
      release-type: python
```

### `reusable-staging-promotion.yml`

Opens (or updates) a PR promoting one branch into another on a schedule. Designed for `development` → `staging` nudges between release cuts, but parameterized so it can promote any pair.

Uses [peter-evans/create-pull-request](https://github.com/peter-evans/create-pull-request). Because that action dedupes by `(base, head)`, the workflow includes a skip check: if an open PR already exists for the same pair and its title starts with `skip-if-title-prefix` (default `release:`), the daily run is a no-op so it doesn't clobber a release-please PR.

**Inputs:** (all optional)

- `head-branch` (default `development`)
- `base-branch` (default `staging`)
- `title` (default `chore: promote development to staging`)
- `body` (default: short automated-promotion note)
- `labels` (default `automated,staging-promotion`)
- `skip-if-title-prefix` (default `release:`; set empty to disable)

**Caller responsibilities:**

- Define the cron / `workflow_dispatch` trigger in the caller.
- Create the labels referenced by `labels` in each consuming repo:
  ```bash
  gh label create automated --color ededed --description "Opened by automation"
  gh label create staging-promotion --color 0e8a16 --description "development → staging promotion"
  ```

**Usage:**

```yaml
name: Daily Staging Promotion
on:
  schedule:
    - cron: "0 16 * * 1-5" # 9am PDT / 8am PST; UTC drifts ±1h across DST
  workflow_dispatch:

jobs:
  promote:
    uses: envoy-ai/ci-workflows/.github/workflows/reusable-staging-promotion.yml@main
```

### `reusable-release-gate.yml`

Fails a `staging` -> `production` promotion PR unless a release was cut since the last one: the `.release-please-manifest.json` version on the PR head must differ from the one on the base. PRs from any other head (hotfixes) skip the job, which counts as passing.

Meant to be a required check on `production` (context: `<caller job id> / Release cut`, e.g. `gate / Release cut`).

**Inputs:** (all optional)

- `manifest-file`: path to `.release-please-manifest.json` (default: repo root)
- `promotion-head`: head branch of promotion PRs (default `staging`)

**Usage:**

```yaml
on:
  pull_request:
    branches: [production]

jobs:
  gate:
    uses: envoy-ai/ci-workflows/.github/workflows/reusable-release-gate.yml@main
```

### `reusable-pr-title-check.yml`

Validates PR titles match [Conventional Commits](https://www.conventionalcommits.org/) format using [amannn/action-semantic-pull-request](https://github.com/amannn/action-semantic-pull-request).

**Allowed prefixes:** `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `perf`, `test`, `ci`, `build`, `revert`

**Usage:**

```yaml
jobs:
  check:
    uses: envoy-ai/ci-workflows/.github/workflows/reusable-pr-title-check.yml@main
```

## Actions

### `claude-implement-ticket` (composite action)

Shared tail for the Linear → Claude autonomous-PR pipeline. Runs [`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action) to implement a ticket end-to-end against repo-specific quality gates, resolves the opened PR, and posts a Slack notification to `#claude-tickets`.

It is a **composite action**, not a reusable workflow, on purpose: each consumer repo's toolchain setup differs (poetry vs npm/wxt) and lives in that repo's own local composite (`setup-python-env`, `setup-build`). A reusable `workflow_call` workflow runs as its own job and cannot reuse a caller's local setup; a composite action runs _inside the caller's already-prepared job_, so the caller installs its toolchain first and this action runs the shared steps on top.

**Caller responsibilities (must run before this action):**

- `actions/checkout` the repo at the target base branch with the App/PAT token (not the default `GITHUB_TOKEN`, so the opened PR triggers CI).
- Run the repo's own toolchain setup so the quality gates are runnable.

**Inputs:**

- `identifier` (required): human ticket id, e.g. `ENG-123`
- `title` (required): ticket title
- `base_branch` (required): branch to base the PR on
- `gate_commands` (required): multiline list of quality-gate commands Claude must pass before opening the PR
- `allowed_tools` (required): `claude-code-action --allowedTools` value
- `anthropic_api_key` / `gh_token` / `slack_webhook_url` (required): secrets, passed in by the caller
- `ticket_id` / `description` / `url` (optional): extra ticket context
- `branch_prefix` (optional, default `claude/`), `model` (default `opus`), `max_turns` (default `60`)

**Usage:**

```yaml
on:
  repository_dispatch:
    types: [linear-ticket]
  workflow_dispatch:

jobs:
  implement:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: development
          token: ${{ secrets.CLAUDE_AGENT_GH_TOKEN }}
      # ... repo-specific toolchain setup here (deps installed, gates runnable) ...
      - uses: envoy-ai/ci-workflows/.github/actions/claude-implement-ticket@main
        with:
          identifier: ${{ github.event.client_payload.identifier || github.event.inputs.identifier }}
          title: ${{ github.event.client_payload.title || github.event.inputs.title }}
          base_branch: development
          gate_commands: |
            - <repo lint command>
            - <repo test command>
          allowed_tools: Read,Edit,Write,Bash(git:*),Bash(gh pr create:*)
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          gh_token: ${{ secrets.CLAUDE_AGENT_GH_TOKEN }}
          slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Branch Rules

Where branch protection lives and how to change it. Two layers, nothing else.

**Org rulesets own policy** (Settings -> Rules -> Rulesets at the org level, apply to every repo, matched by branch name so the branch layout of a repo doesn't matter):

| Ruleset                                 | Branches                       | Rules                                                             |
| --------------------------------------- | ------------------------------ | ----------------------------------------------------------------- |
| Default (development) branch protection | default branch + `development` | PR required, 1 approval, linear history, no force-push, no delete |
| Staging branch protection               | `staging`                      | PR required, 0 approvals, no force-push, no delete                |
| Production branch protection            | `production`                   | PR required, 1 approval, no force-push, no delete                 |

Approvals survive new pushes (stale reviews are not dismissed).

No bypass actors anywhere. Rulesets apply to admins unconditionally.

**Repo rulesets own required status checks only.** One per repo per branch that has CI (`<repo> required checks (development)`, `Production required checks`). Job names in there must match the workflow job `name:` exactly; a renamed job blocks every PR on "Expected".

**Classic branch protection (Settings -> Branches) is not used.** It was removed org-wide on 2026-08-25. It layers with rulesets (most restrictive wins) and silently re-imposed reviews on staging, so don't add it back. Note the Vanta test "branch protection rules are enforced for administrators" reads only classic protection and cannot see rulesets.

Changing policy = edit the org ruleset. Changing checks = edit the repo ruleset. Inspect what actually applies to a branch:

```bash
gh api repos/envoy-ai/<repo>/rules/branches/<branch>
```

## PR Title Format

Since all repos use **squash merge** with the PR title as the commit message, only the PR title needs to follow conventional commits. Individual commits inside the PR don't matter.

```
type(scope): description

Examples:
  feat(api): add user avatar upload
  fix(scheduler): correct timezone handling
  chore(deps): bump fastapi to 0.115
  refactor: simplify load matching logic
```

### How it maps to version bumps

| Prefix                       | Version Bump  | Example         |
| ---------------------------- | ------------- | --------------- |
| `feat`                       | Minor (1.x.0) | New feature     |
| `fix`                        | Patch (1.0.x) | Bug fix         |
| `feat!` or `BREAKING CHANGE` | Major (x.0.0) | Breaking change |
| `chore`, `docs`, `ci`, etc.  | No bump       | Maintenance     |
