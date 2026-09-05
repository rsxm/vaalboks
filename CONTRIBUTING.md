# Contributing

## Development setup

Python 3.14 and uv are required. Install dependencies and quality tools with:

```sh
uv sync --all-groups
bun install --frozen-lockfile
```

Run the application locally:

```sh
uv run vaalboks --http
```

## Checks

Run the same checks used by CI before opening a pull request:

```sh
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python manage.py test
bun run check
```

Keep changes focused, add regression tests for behavior changes, and do not
commit runtime data, generated certificates, or uploaded files.
