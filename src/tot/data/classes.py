"""2024 PHB (5.5e) 職業顯示資料：12 職業的中文名、說明、裝備、戲法/法術等。

此模組僅供 TUI 顯示用，不影響 Bone Engine 的 ClassData / CLASS_REGISTRY。
資料來源：docs/2024_translate/phb/ch3_01~12_*.md
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassDisplayData:
    """職業的顯示與建角用資料（補充 bone_engine ClassData 缺少的欄位）。"""

    id: str  # 英文 key，對應 CLASS_REGISTRY 的 key
    name_zh: str
    name_en: str
    description: str  # 1~2 句中文簡述
    complexity: str  # "低" / "中等" / "高"
    armor_training: tuple[str, ...]  # 護甲訓練（如 ("輕甲", "中甲", "盾牌")）
    weapon_training: tuple[str, ...]  # 武器訓練
    equipment_a: str  # 起始裝備選項 A
    equipment_b: str  # 起始裝備選項 B
    default_armor: str = "none"  # 1 級預設護甲："light"/"medium"/"heavy"/"none"
    num_cantrips: int = 0  # 1 級戲法數量
    num_prepared_spells: int = 0  # 1 級備妥法術數量
    features_1st: tuple[str, ...] = ()  # 1 級職業特性名稱


CLASS_DISPLAY: dict[str, ClassDisplayData] = {
    "Barbarian": ClassDisplayData(
        id="Barbarian",
        name_zh="野蠻人",
        name_en="Barbarian",
        description="以原始之怒投入戰鬥的狂戰士，擅長承受傷害和造成破壞。",
        complexity="低",
        armor_training=("輕甲", "中甲", "盾牌"),
        weapon_training=("簡易武器", "軍用武器"),
        equipment_a="巨斧、手斧×4、探險者背包、15 GP",
        equipment_b="75 GP",
        default_armor="none",  # 無甲防禦
        features_1st=("狂暴", "無甲防禦", "武器精通"),
    ),
    "Bard": ClassDisplayData(
        id="Bard",
        name_zh="吟遊詩人",
        name_en="Bard",
        description="以音樂和言語編織魔法的多才表演者，能鼓舞盟友並迷惑敵人。",
        complexity="中等",
        armor_training=("輕甲",),
        weapon_training=("簡易武器",),
        equipment_a="皮甲、匕首×2、樂器、藝人背包、19 GP",
        equipment_b="90 GP",
        default_armor="light",
        num_cantrips=2,
        num_prepared_spells=4,
        features_1st=("吟遊鼓舞", "施法"),
    ),
    "Cleric": ClassDisplayData(
        id="Cleric",
        name_zh="牧師",
        name_en="Cleric",
        description="信仰神祇的神聖使者，能治癒傷口、驅逐不死並召喚神聖之力。",
        complexity="中等",
        armor_training=("輕甲", "中甲", "盾牌"),
        weapon_training=("簡易武器",),
        equipment_a="鏈甲衫、盾牌、錘矛、聖徽、牧師背包、7 GP",
        equipment_b="110 GP",
        default_armor="medium",
        num_cantrips=3,
        num_prepared_spells=4,
        features_1st=("施法", "神聖秩序"),
    ),
    "Druid": ClassDisplayData(
        id="Druid",
        name_zh="德魯伊",
        name_en="Druid",
        description="自然之力的守護者，運用原始魔法變形、治癒並操控元素。",
        complexity="中等",
        armor_training=("輕甲", "盾牌"),
        weapon_training=("簡易武器",),
        equipment_a="皮甲、盾牌、鐮刀、德魯伊法器（長棍）、探險者背包、草藥工具、9 GP",
        equipment_b="50 GP",
        default_armor="light",
        num_cantrips=2,
        num_prepared_spells=4,
        features_1st=("施法", "德魯伊語", "原初秩序"),
    ),
    "Fighter": ClassDisplayData(
        id="Fighter",
        name_zh="戰士",
        name_en="Fighter",
        description="精通各種武器和護甲的武藝大師，在戰場上無人能出其右。",
        complexity="低",
        armor_training=("輕甲", "中甲", "重甲", "盾牌"),
        weapon_training=("簡易武器", "軍用武器"),
        equipment_a="鏈甲、巨劍、連枷、標槍×8、地城者背包、4 GP",
        equipment_b="155 GP",
        default_armor="heavy",
        features_1st=("戰鬥風格", "第二風", "武器精通"),
    ),
    "Monk": ClassDisplayData(
        id="Monk",
        name_zh="武僧",
        name_en="Monk",
        description="以徒手戰鬥和集氣之力追求身心完美的修行者。",
        complexity="中等",
        armor_training=(),
        weapon_training=("簡易武器", "輕型軍用武器"),
        equipment_a="矛、匕首×5、工具或樂器、探險者背包、11 GP",
        equipment_b="50 GP",
        default_armor="none",  # 無甲防禦
        features_1st=("武術", "無甲防禦"),
    ),
    "Paladin": ClassDisplayData(
        id="Paladin",
        name_zh="聖騎士",
        name_en="Paladin",
        description="以神聖誓約和聖療之力守護盟友、懲擊邪惡的重甲戰士。",
        complexity="中等",
        armor_training=("輕甲", "中甲", "重甲", "盾牌"),
        weapon_training=("簡易武器", "軍用武器"),
        equipment_a="鏈甲、盾牌、長劍、標槍×6、聖徽、牧師背包、9 GP",
        equipment_b="150 GP",
        default_armor="heavy",
        num_prepared_spells=2,
        features_1st=("聖療術", "施法", "武器精通"),
    ),
    "Ranger": ClassDisplayData(
        id="Ranger",
        name_zh="遊俠",
        name_en="Ranger",
        description="精通求生與追蹤的荒野戰士，擅長遠程攻擊並運用自然魔法。",
        complexity="中等",
        armor_training=("輕甲", "中甲", "盾牌"),
        weapon_training=("簡易武器", "軍用武器"),
        equipment_a="鑲釘皮甲、彎刀、短劍、長弓、箭×20、箭袋、德魯伊法器、探險者背包、7 GP",
        equipment_b="150 GP",
        default_armor="medium",
        num_prepared_spells=2,
        features_1st=("施法", "宿敵", "武器精通"),
    ),
    "Rogue": ClassDisplayData(
        id="Rogue",
        name_zh="游蕩者",
        name_en="Rogue",
        description="以隱匿和精準打擊見長的技巧型戰士，擅長偷襲和技能運用。",
        complexity="中等",
        armor_training=("輕甲",),
        weapon_training=("簡易武器", "靈巧/輕型軍用武器"),
        equipment_a="皮甲、匕首×2、短劍、短弓、箭×20、箭袋、盜賊工具、竊盜者背包、8 GP",
        equipment_b="100 GP",
        default_armor="light",
        features_1st=("專精", "偷襲", "盜賊暗語", "武器精通"),
    ),
    "Sorcerer": ClassDisplayData(
        id="Sorcerer",
        name_zh="術士",
        name_en="Sorcerer",
        description="天生就擁有魔法力量的施法者，能以直覺引導強大的元素之力。",
        complexity="中等",
        armor_training=(),
        weapon_training=("簡易武器",),
        equipment_a="矛、匕首×2、奧術法器（水晶）、探險者背包、28 GP",
        equipment_b="50 GP",
        default_armor="none",
        num_cantrips=4,
        num_prepared_spells=2,
        features_1st=("施法", "天生法術"),
    ),
    "Warlock": ClassDisplayData(
        id="Warlock",
        name_zh="契術師",
        name_en="Warlock",
        description="與超自然存在訂約以獲取禁忌知識和魔力的神祕施法者。",
        complexity="高",
        armor_training=("輕甲",),
        weapon_training=("簡易武器",),
        equipment_a="皮甲、鐮刀、匕首×2、奧術法器（水晶球）、書籍（神祕學）、學者背包、15 GP",
        equipment_b="100 GP",
        default_armor="light",
        num_cantrips=2,
        num_prepared_spells=2,
        features_1st=("魔能祈喚", "契約魔法"),
    ),
    "Wizard": ClassDisplayData(
        id="Wizard",
        name_zh="法師",
        name_en="Wizard",
        description="透過研習法術書精通奧術的學者，擁有最廣泛的法術選擇。",
        complexity="高",
        armor_training=(),
        weapon_training=("簡易武器",),
        equipment_a="匕首×2、奧術法器（長杖）、法袍、法術書、學者背包、5 GP",
        equipment_b="55 GP",
        default_armor="none",
        num_cantrips=3,
        num_prepared_spells=4,
        features_1st=("施法", "儀式行者", "奧術恢復"),
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# 各職業標準陣列建議分配（ch2 §3 表格）
# ─────────────────────────────────────────────────────────────────────────────

# key=職業 id, value=(STR, DEX, CON, INT, WIS, CHA)
STANDARD_ARRAY_SUGGESTION: dict[str, tuple[int, ...]] = {
    "Barbarian": (15, 13, 14, 10, 12, 8),
    "Bard": (8, 14, 12, 13, 10, 15),
    "Cleric": (14, 8, 13, 10, 15, 12),
    "Druid": (8, 12, 14, 13, 15, 10),
    "Fighter": (15, 14, 13, 8, 10, 12),
    "Monk": (12, 15, 13, 10, 14, 8),
    "Paladin": (15, 10, 13, 8, 12, 14),
    "Ranger": (12, 15, 13, 8, 14, 10),
    "Rogue": (12, 15, 13, 14, 10, 8),
    "Sorcerer": (10, 13, 14, 8, 12, 15),
    "Warlock": (8, 14, 13, 12, 10, 15),
    "Wizard": (8, 12, 13, 15, 14, 10),
}
