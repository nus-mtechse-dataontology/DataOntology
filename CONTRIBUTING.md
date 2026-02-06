# Contributing

Thanks for contributing to DataOntology.

## Quick workflow
1. Create a branch for your change.
2. Write or update tests first.
3. Implement changes following the contracts in `app/models/`.
4. Run formatting/lint and tests locally.
5. Open a PR with a short summary and testing notes.

## Tests
```bash
uv run pytest
```

## Lint
```bash
uv run ruff check .
```

## Style notes
- Prefer small, focused commits.
- Keep public contracts stable; update docs and tests if you change them.
- Add or update tests for new behavior and edge cases.
