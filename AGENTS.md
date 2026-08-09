# image-processor

## Tooling

- Python tooling is managed via `uv`. Run CLI tools with `uv run <tool>` (or `uv tool run --from <pkg> <tool>` for one-offs) — do not assume tools are globally installed or install via pip/pipx/brew.
- Pre-commit hooks are configured in `.pre-commit-config.yaml`. Two hook stages are installed: the default (`pre-commit`) for file checks, and `commit-msg` for conventional-commit message linting. Run `uv run pre-commit run --all-files` to check everything manually.
