#!/usr/bin/env bash
# T.O.T. TUI 探索試玩啟動腳本
# 用法：./explore.sh [地圖名]
#   無參數 → 顯示互動選單
#   有參數 → 直接啟動指定地圖

set -e
cd "$(dirname "$0")"

echo ""
echo "  🐙 T.O.T. - The Octo-Teller 探索系統"
echo "  ======================================="
echo ""

# 如果有參數，直接啟動
if [ -n "$1" ]; then
    echo "  載入地圖：$1"
    echo ""
    exec uv run --extra tui python -m tot.tui.exploration "$1"
fi

# 互動選單
echo "  地圖層級："
echo ""
echo "  🌍 世界地圖"
echo "    [1] wilderness  林間小徑（世界探索）"
echo ""
echo "  🏰 城鎮"
echo "    [2] town        河谷鎮（城鎮 POI 探索）"
echo ""
echo "  ⚔️  地城"
echo "    [3] dungeon     教學地牢（Pointcrawl + area）"
echo "    [4] ruins       崖岸遺跡（跳躍/攀爬/暗門）"
echo ""
echo "  ──────────────────────────────"
echo "  世界 → 城鎮/地城 → 區域(area)"
echo "  wilderness → town, cliff_ruins"
echo "  dungeon → tutorial_room (area)"
echo "  ruins → cave_explore (area)"
echo "  ──────────────────────────────"
echo ""
read -rp "  選擇 [1-4]（預設 4）：" choice
echo ""

case "$choice" in
    1) map="wilderness" ;;
    2) map="town" ;;
    3) map="dungeon" ;;
    4|"") map="ruins" ;;
    *)
        echo "  未知選項：$choice"
        exit 1
        ;;
esac

echo "  載入地圖：$map"
echo ""
exec uv run --extra tui python -m tot.tui.exploration "$map"
