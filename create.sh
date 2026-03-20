#!/usr/bin/env bash
cd "$(dirname "$0")"
exec uv run python -m tot.tui.character_creation "$@"
