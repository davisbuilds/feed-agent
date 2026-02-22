# Contributing

This repository uses a squash-merge workflow to keep `main` history clean and readable.

## Workflow

1. Sync local `main`.
2. Create a feature branch from `main`.
3. Make focused changes and commit normally.
4. Push branch and open a pull request.
5. Merge with **Squash and merge** after CI passes.
6. Let GitHub auto-delete the merged remote branch.
7. Prune merged local branches periodically.

## Branch Naming

Use descriptive prefixes:

- `feat/<name>`
- `fix/<name>`
- `chore/<name>`
- `docs/<name>`

## Commit Guidance

- Keep commits logical and atomic while working on the branch.
- Use clear, imperative commit messages.
- It is fine to have multiple commits in one PR; squash merge will combine them on `main`.

## Pull Request Expectations

- Keep PR scope tight (one objective per PR).
- Include a short summary and test evidence.
- Ensure CI passes before merge:
  - `uv run ruff check .`
  - `uv run python -m pytest`

CI is configured in `.github/workflows/`.

## Local Branch Cleanup

Run periodically:

```bash
git fetch --prune
git branch --merged main | grep -v ' main$' | xargs -n 1 git branch -d
```

## Documentation Hygiene

- Do not hardcode volatile counts in docs.
- Prefer executable source-of-truth references (for example, `uv run python -m pytest`, `.github/workflows/`).

## Related Docs

- Git history and branch hygiene config: `docs/GIT_HISTORY_POLICY.md`
- Agent implementation guidance: `AGENTS.md`
- Project onboarding: `README.md`
