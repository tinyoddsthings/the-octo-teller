#!/bin/bash
# D&D 翻譯術語一致性驗證腳本
# 掃描 PHB/DMG/MM 三本書，確認不應出現的舊術語已全部修正

BASE="$(cd "$(dirname "$0")" && pwd)"
FAIL=0

check() {
    local label="$1"
    local pattern="$2"
    local count
    count=$(grep -rn "$pattern" "$BASE/phb/" "$BASE/dmg/" "$BASE/mm/" --include='*.md' 2>/dev/null | grep -v 'todo.md' | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        echo "❌ $label: 發現 $count 處"
        grep -rn "$pattern" "$BASE/phb/" "$BASE/dmg/" "$BASE/mm/" --include='*.md' 2>/dev/null | grep -v 'todo.md' | head -5
        echo ""
        FAIL=1
    else
        echo "✅ $label: 0 處"
    fi
}

echo "=== D&D 翻譯術語一致性驗證 ==="
echo ""

echo "--- 舊距離單位 ---"
check "「呎」（應為 m）" "呎"
check "「公尺」（應為 m）" "公尺"

echo ""
echo "--- 舊術語 ---"
check "「體魄」（應為體質）" "體魄"
check "「精靈荒野」（應為妖精荒野）" "精靈荒野"
check "「資料方塊」（應為數據表）" "資料方塊"
check "「異形」（應為異怪）" "異形"

echo ""
echo "--- 英文狀態名稱（不應獨立出現）---"
# 排除雙語格式如「目盲（Blinded）」
for cond in Prone Grappled Restrained Stunned Frightened Charmed Poisoned Blinded Paralyzed Petrified Incapacitated Exhaustion Invisible Unconscious Deafened; do
    count=$(grep -rn "\b${cond}\b" "$BASE/phb/" "$BASE/dmg/" "$BASE/mm/" --include='*.md' 2>/dev/null \
        | grep -v 'todo.md' \
        | grep -v "（${cond}）" \
        | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        echo "⚠️  $cond: $count 處（非雙語格式）"
        grep -rn "\b${cond}\b" "$BASE/phb/" "$BASE/dmg/" "$BASE/mm/" --include='*.md' 2>/dev/null \
            | grep -v 'todo.md' \
            | grep -v "（${cond}）" \
            | head -3
        echo ""
    else
        echo "✅ $cond: 0 處"
    fi
done

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "🎉 所有舊術語檢查通過！"
else
    echo "⚠️  有術語需要修正，請查看上方標記 ❌ 的項目"
fi
