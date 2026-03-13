#!/usr/bin/env bash
# T.O.T. TUI 戰鬥試玩啟動腳本
# 用法：./play.sh

set -e

cd "$(dirname "$0")"

echo "🐙 T.O.T. - The Octo-Teller"
echo "載入戰鬥 TUI..."
echo ""

uv run --extra tui python -m tot.tui
