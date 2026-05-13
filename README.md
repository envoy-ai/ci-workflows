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
    - cron: "0 16 * * 1-5"  # 9am PDT / 8am PST; UTC drifts ±1h across DST
  workflow_dispatch:

jobs:
  promote:
    uses: envoy-ai/ci-workflows/.github/workflows/reusable-staging-promotion.yml@main
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
