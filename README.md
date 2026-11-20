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

### `linear-ticket.yml` (organization required workflow)

Fails a PR that names no Linear issue. The issue key (`ENG-1234`) may sit in the branch name (Linear's "Copy git branch name"), the PR title, or the PR body; any one of them is how Linear links the PR to the issue. Exempt: PRs opened by a bot (release-please, the staging promotion, dependabot) and a person's promotion PR whose head is `development`, `staging` or `production`.

It is not a reusable workflow and no repository calls it. The organization ruleset **Default (development) branch protection** requires it through the rule "Require workflows to pass before merging", which runs this file from `main` against every repository's default branch, so a new repository is covered the day it is created. Ruleset workflows run only on `opened`, `synchronize` and `reopened` (event filters are ignored), so a key added to the title or body after the first run is checked on the next push, or on a close and reopen.

The check name is `Linked to a Linear ticket`. Adding a Linear team is the `TEAM_KEYS` constant in the workflow.

## Actions

### `release-notify` (composite action)

Posts a production release to Slack from the workflow that puts it live. Release-please cuts releases on `development`, so a GitHub Release exists long before the code reaches `production`; this action runs at the end of each repo's production deploy instead, and its message is the release-please changelog that landed with that push: the lines added to `CHANGELOG.md` between the previous tip of the branch (`HEAD^1`) and `HEAD`, converted to Slack mrkdwn. A promotion carrying several releases lists all of them. Each entry ends with who shipped it: the author of its squash commit (the PR author), linked to their GitHub profile, resolved through the commits API with the job's token. A hotfix merged without a version bump posts the commit subject. Failures post a one-line notice with the run link.

**Caller responsibilities:**

- Check out with `fetch-depth: 2` or more (the changelog diff needs `HEAD^1`).
- Give the job `contents: read` (the default), which is what the author lookup needs.
- Run it under `if: always()` and pass `status: ${{ job.status }}`, so a failed deploy is announced too.
- Gate it to production in the caller (`github.ref_name == 'production'`, the resolved environment, …).
- Pass the channel webhook: the org secret `SLACK_RELEASES_WEBHOOK_URL` (`#releases`). Incoming webhooks are channel-bound, so a different channel is a different webhook and secret.

**Inputs:**

- `webhook` (required): Slack incoming-webhook URL
- `status` (default `success`): outcome to report
- `environment` (default `production`): name used in the message
- `mode` (default `release`): `release` reads the changelog diff; `image` names a deployed image tag and skips it (rollbacks, manual dispatches)
- `image-tag`: the tag for `image` mode
- `headline`: replaces the success verb phrase, e.g. `submitted to the Chrome Web Store, publishes on Google approval`
- `manifest-file` / `changelog-file`: release-please file paths (defaults at the repo root)

**Usage:**

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 2
# ... deploy steps ...
- name: Notify #releases
  if: always() && github.ref_name == 'production'
  uses: envoy-ai/ci-workflows/.github/actions/release-notify@main
  with:
    webhook: ${{ secrets.SLACK_RELEASES_WEBHOOK_URL }}
    status: ${{ job.status }}
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
