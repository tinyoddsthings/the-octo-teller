#!/usr/bin/env bash
# T.O.T. TUI 探索試玩啟動腳本
# 用法：./explore.sh

set -e

cd "$(dirname "$0")"

echo "🐙 T.O.T. - The Octo-Teller"
echo "載入探索 TUI..."
echo ""

uv run --extra tui python -m tot.tui.exploration
