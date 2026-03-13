"""遊戲動作時間消耗常數（秒）。

所有消耗時間的動作統一定義在此，供 exploration.py / rest.py 等模組使用。
D&D 規則基準：1 輪 = 6 秒。
"""

# ── 戰鬥 ──
COMBAT_ROUND = 6  # 1 輪 = 6 秒

# ── 探索動作 ──
LOCKPICK = 60  # 開鎖嘗試（約 10 輪）
FORCE_DOOR = 6  # 破門（1 輪）
SEARCH_ROOM_DUNGEON = 600  # 地城房間搜索（10 分鐘）
SEARCH_ROOM_TOWN = 3600  # 城鎮建築搜索（1 小時）

# ── 休息 ──
SHORT_REST = 3600  # 短休 = 1 小時
LONG_REST = 28800  # 長休 = 8 小時

# ── 法術 ──
RITUAL_BASE = 600  # 儀式施法基礎 = 10 分鐘

# ── 移動（地城層 edge 預設） ──
DUNGEON_MOVE_DEFAULT = 60  # 地城走廊預設 1 分鐘
TOWN_MOVE_DEFAULT = 1800  # 城鎮街道預設 30 分鐘
