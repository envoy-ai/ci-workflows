# ci-workflows

Shared reusable GitHub Actions workflows for EnvoyAI repositories.

## Repository Settings (configure after creating on GitHub)

This repo is **public** so other private EnvoyAI repos can reference its workflows. Lock it down:

- **Settings > General**: Disable Issues, Wiki, Discussions, Projects
- **Settings > Collaborators**: No outside collaborators. Only `@envoy-ai/developers` team.
- **Settings > Branches > `main`**: Require PR with 1 approval, require CODEOWNERS review, no direct push
- **Settings > Actions > General**: Set "Fork pull request workflows" to "Require approval for all outside collaborators"

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
