# Quiver

Universal ADBC query tool - explore Arrow database connectivity across multiple backends.

## Installation

```bash
# Install with uv
uv sync

# Install with all backends
uv sync --all-extras
```

## Usage

```bash
# Show help
quiver --help

# Show version
quiver --version

# List available backends
quiver backends
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run linting
uv run ruff check src tests

# Run type checking
uv run mypy src
```

## License

MIT
