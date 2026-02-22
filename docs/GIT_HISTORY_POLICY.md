# Git History and Branch Hygiene

Last updated: February 22, 2026

## Repository Merge Settings

Configured on GitHub repository `davisbuilds/feed`:

- `allow_squash_merge`: `true`
- `allow_merge_commit`: `false`
- `allow_rebase_merge`: `false`
- `delete_branch_on_merge`: `true`
- `squash_merge_commit_title`: `PR_TITLE`
- `squash_merge_commit_message`: `PR_BODY`

Result:

- PR branches can contain multiple commits.
- `main` receives one squashed commit per merged PR.
- Merged remote branches are auto-deleted.

## Merge Strategy

Squash-merge only. All other merge strategies are disabled at the repository level.

## CI Gates

CI is configured in `.github/workflows/`. Quality gates before merge:

- `uv run ruff check .`
- `uv run python -m pytest`

## Current Limitation

`main` branch protection is not enabled because GitHub returned `403` for branch protection APIs on this private repository tier. Until upgraded, enforce checks and review discipline by team convention.

## Recommended Ongoing Hygiene

1. Create short-lived feature branches from `main`.
2. Open PRs early; keep them focused.
3. Merge only with **Squash and merge** after CI passes.
4. Periodically prune local branches:

```bash
git fetch --prune
git branch --merged main | grep -v ' main$' | xargs -n 1 git branch -d
```
