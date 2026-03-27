"""T.O.T. 裝備資料庫：武器、護甲、消耗品、裝備包。

資料來源：D&D 2024 PHB (5.5e) 武器與裝甲表格。
距離單位：公尺（5ft = 1.5m）。
"""

from __future__ import annotations

from dataclasses import dataclass

from tot.models.creature import Weapon
from tot.models.enums import DamageType, WeaponMastery, WeaponProperty

# ─────────────────────────────────────────────────────────────────────────────
# 武器資料庫（14 簡易 + 24 軍用 = 38 種）
# ─────────────────────────────────────────────────────────────────────────────
#
# range_normal：近戰 = 1.5m、長觸 = 3.0m、遠程/投擲 = 基本射程
# range_long：投擲/遠程武器的長射程（公尺）

WEAPON_REGISTRY: dict[str, Weapon] = {
    # ── 簡易近戰（10 種） ──────────────────────────────────────────────────
    "Club": Weapon(
        name="棍棒",
        en_name="Club",
        damage_dice="1d4",
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.LIGHT],
        range_normal=1.5,
        mastery=WeaponMastery.SLOW,
        weight=2.0,
        cost_gp=0.1,
    ),
    "Dagger": Weapon(
        name="匕首",
        en_name="Dagger",
        damage_dice="1d4",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.THROWN],
        range_normal=1.5,
        range_long=18.0,
        mastery=WeaponMastery.NICK,
        weight=1.0,
        cost_gp=2.0,
    ),
    "Greatclub": Weapon(
        name="巨棒",
        en_name="Greatclub",
        damage_dice="1d8",
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.TWO_HANDED],
        range_normal=1.5,
        mastery=WeaponMastery.PUSH,
        weight=10.0,
        cost_gp=0.2,
    ),
    "Handaxe": Weapon(
        name="手斧",
        en_name="Handaxe",
        damage_dice="1d6",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.LIGHT, WeaponProperty.THROWN],
        range_normal=1.5,
        range_long=18.0,
        mastery=WeaponMastery.VEX,
        weight=2.0,
        cost_gp=5.0,
    ),
    "Javelin": Weapon(
        name="標槍",
        en_name="Javelin",
        damage_dice="1d6",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.THROWN],
        range_normal=1.5,
        range_long=36.0,
        mastery=WeaponMastery.SLOW,
        weight=2.0,
        cost_gp=0.5,
    ),
    "Light Hammer": Weapon(
        name="輕錘",
        en_name="Light Hammer",
        damage_dice="1d4",
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.LIGHT, WeaponProperty.THROWN],
        range_normal=1.5,
        range_long=18.0,
        mastery=WeaponMastery.NICK,
        weight=2.0,
        cost_gp=2.0,
    ),
    "Mace": Weapon(
        name="錘矛",
        en_name="Mace",
        damage_dice="1d6",
        damage_type=DamageType.BLUDGEONING,
        properties=[],
        range_normal=1.5,
        mastery=WeaponMastery.SAP,
        weight=4.0,
        cost_gp=5.0,
    ),
    "Quarterstaff": Weapon(
        name="木棍",
        en_name="Quarterstaff",
        damage_dice="1d6",
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.VERSATILE],
        range_normal=1.5,
        mastery=WeaponMastery.TOPPLE,
        versatile_dice="1d8",
        weight=4.0,
        cost_gp=0.2,
    ),
    "Sickle": Weapon(
        name="鐮刀",
        en_name="Sickle",
        damage_dice="1d4",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.LIGHT],
        range_normal=1.5,
        mastery=WeaponMastery.NICK,
        weight=2.0,
        cost_gp=1.0,
    ),
    "Spear": Weapon(
        name="矛",
        en_name="Spear",
        damage_dice="1d6",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.THROWN, WeaponProperty.VERSATILE],
        range_normal=1.5,
        range_long=18.0,
        mastery=WeaponMastery.SAP,
        versatile_dice="1d8",
        weight=3.0,
        cost_gp=1.0,
    ),
    # ── 簡易遠程（4 種） ──────────────────────────────────────────────────
    "Dart": Weapon(
        name="飛鏢",
        en_name="Dart",
        damage_dice="1d4",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.THROWN],
        range_normal=6.0,
        range_long=18.0,
        mastery=WeaponMastery.VEX,
        weight=0.25,
        cost_gp=0.05,
    ),
    "Light Crossbow": Weapon(
        name="輕弩",
        en_name="Light Crossbow",
        damage_dice="1d8",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.AMMUNITION, WeaponProperty.LOADING, WeaponProperty.TWO_HANDED],
        range_normal=24.0,
        range_long=96.0,
        mastery=WeaponMastery.SLOW,
        weight=5.0,
        cost_gp=25.0,
    ),
    "Shortbow": Weapon(
        name="短弓",
        en_name="Shortbow",
        damage_dice="1d6",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.AMMUNITION, WeaponProperty.TWO_HANDED],
        range_normal=24.0,
        range_long=96.0,
        mastery=WeaponMastery.VEX,
        weight=2.0,
        cost_gp=25.0,
    ),
    "Sling": Weapon(
        name="投石索",
        en_name="Sling",
        damage_dice="1d4",
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.AMMUNITION],
        range_normal=9.0,
        range_long=36.0,
        mastery=WeaponMastery.SLOW,
        weight=0.0,
        cost_gp=0.1,
    ),
    # ── 軍用近戰（18 種） ─────────────────────────────────────────────────
    "Battleaxe": Weapon(
        name="戰斧",
        en_name="Battleaxe",
        damage_dice="1d8",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.VERSATILE],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.TOPPLE,
        versatile_dice="1d10",
        weight=4.0,
        cost_gp=10.0,
    ),
    "Flail": Weapon(
        name="連枷",
        en_name="Flail",
        damage_dice="1d8",
        damage_type=DamageType.BLUDGEONING,
        properties=[],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.SAP,
        weight=2.0,
        cost_gp=10.0,
    ),
    "Glaive": Weapon(
        name="關刀",
        en_name="Glaive",
        damage_dice="1d10",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.REACH, WeaponProperty.TWO_HANDED],
        range_normal=3.0,
        is_martial=True,
        mastery=WeaponMastery.GRAZE,
        weight=6.0,
        cost_gp=20.0,
    ),
    "Greataxe": Weapon(
        name="巨斧",
        en_name="Greataxe",
        damage_dice="1d12",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.TWO_HANDED],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.CLEAVE,
        weight=7.0,
        cost_gp=30.0,
    ),
    "Greatsword": Weapon(
        name="巨劍",
        en_name="Greatsword",
        damage_dice="2d6",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.TWO_HANDED],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.GRAZE,
        weight=6.0,
        cost_gp=50.0,
    ),
    "Halberd": Weapon(
        name="戟",
        en_name="Halberd",
        damage_dice="1d10",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.REACH, WeaponProperty.TWO_HANDED],
        range_normal=3.0,
        is_martial=True,
        mastery=WeaponMastery.CLEAVE,
        weight=6.0,
        cost_gp=20.0,
    ),
    "Lance": Weapon(
        name="騎槍",
        en_name="Lance",
        damage_dice="1d10",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.REACH, WeaponProperty.TWO_HANDED],
        range_normal=3.0,
        is_martial=True,
        mastery=WeaponMastery.TOPPLE,
        weight=6.0,
        cost_gp=10.0,
    ),
    "Longsword": Weapon(
        name="長劍",
        en_name="Longsword",
        damage_dice="1d8",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.VERSATILE],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.SAP,
        versatile_dice="1d10",
        weight=3.0,
        cost_gp=15.0,
    ),
    "Maul": Weapon(
        name="巨槌",
        en_name="Maul",
        damage_dice="2d6",
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.TWO_HANDED],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.TOPPLE,
        weight=10.0,
        cost_gp=10.0,
    ),
    "Morningstar": Weapon(
        name="釘頭錘",
        en_name="Morningstar",
        damage_dice="1d8",
        damage_type=DamageType.PIERCING,
        properties=[],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.SAP,
        weight=4.0,
        cost_gp=15.0,
    ),
    "Pike": Weapon(
        name="長矛",
        en_name="Pike",
        damage_dice="1d10",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.REACH, WeaponProperty.TWO_HANDED],
        range_normal=3.0,
        is_martial=True,
        mastery=WeaponMastery.PUSH,
        weight=18.0,
        cost_gp=5.0,
    ),
    "Rapier": Weapon(
        name="刺劍",
        en_name="Rapier",
        damage_dice="1d8",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.VEX,
        weight=2.0,
        cost_gp=25.0,
    ),
    "Scimitar": Weapon(
        name="彎刀",
        en_name="Scimitar",
        damage_dice="1d6",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.NICK,
        weight=3.0,
        cost_gp=25.0,
    ),
    "Shortsword": Weapon(
        name="短劍",
        en_name="Shortsword",
        damage_dice="1d6",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.VEX,
        weight=2.0,
        cost_gp=10.0,
    ),
    "Trident": Weapon(
        name="三叉戟",
        en_name="Trident",
        damage_dice="1d8",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.THROWN, WeaponProperty.VERSATILE],
        range_normal=1.5,
        range_long=18.0,
        is_martial=True,
        mastery=WeaponMastery.TOPPLE,
        versatile_dice="1d10",
        weight=4.0,
        cost_gp=5.0,
    ),
    "War Pick": Weapon(
        name="戰鎬",
        en_name="War Pick",
        damage_dice="1d8",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.VERSATILE],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.SAP,
        versatile_dice="1d10",
        weight=2.0,
        cost_gp=5.0,
    ),
    "Warhammer": Weapon(
        name="戰錘",
        en_name="Warhammer",
        damage_dice="1d8",
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.VERSATILE],
        range_normal=1.5,
        is_martial=True,
        mastery=WeaponMastery.PUSH,
        versatile_dice="1d10",
        weight=2.0,
        cost_gp=15.0,
    ),
    "Whip": Weapon(
        name="鞭",
        en_name="Whip",
        damage_dice="1d4",
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.REACH],
        range_normal=3.0,
        is_martial=True,
        mastery=WeaponMastery.SLOW,
        weight=3.0,
        cost_gp=2.0,
    ),
    # ── 軍用遠程（6 種） ──────────────────────────────────────────────────
    "Blowgun": Weapon(
        name="吹箭筒",
        en_name="Blowgun",
        damage_dice="1",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.AMMUNITION, WeaponProperty.LOADING],
        range_normal=7.5,
        range_long=30.0,
        is_martial=True,
        mastery=WeaponMastery.VEX,
        weight=1.0,
        cost_gp=10.0,
    ),
    "Hand Crossbow": Weapon(
        name="手弩",
        en_name="Hand Crossbow",
        damage_dice="1d6",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.AMMUNITION, WeaponProperty.LIGHT, WeaponProperty.LOADING],
        range_normal=9.0,
        range_long=36.0,
        is_martial=True,
        mastery=WeaponMastery.VEX,
        weight=3.0,
        cost_gp=75.0,
    ),
    "Heavy Crossbow": Weapon(
        name="重弩",
        en_name="Heavy Crossbow",
        damage_dice="1d10",
        damage_type=DamageType.PIERCING,
        properties=[
            WeaponProperty.AMMUNITION,
            WeaponProperty.HEAVY,
            WeaponProperty.LOADING,
            WeaponProperty.TWO_HANDED,
        ],
        range_normal=30.0,
        range_long=120.0,
        is_martial=True,
        mastery=WeaponMastery.PUSH,
        weight=18.0,
        cost_gp=50.0,
    ),
    "Longbow": Weapon(
        name="長弓",
        en_name="Longbow",
        damage_dice="1d8",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.AMMUNITION, WeaponProperty.HEAVY, WeaponProperty.TWO_HANDED],
        range_normal=45.0,
        range_long=180.0,
        is_martial=True,
        mastery=WeaponMastery.SLOW,
        weight=2.0,
        cost_gp=50.0,
    ),
    "Musket": Weapon(
        name="火槍",
        en_name="Musket",
        damage_dice="1d12",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.AMMUNITION, WeaponProperty.LOADING, WeaponProperty.TWO_HANDED],
        range_normal=12.0,
        range_long=36.0,
        is_martial=True,
        mastery=WeaponMastery.SLOW,
        weight=10.0,
        cost_gp=500.0,
    ),
    "Pistol": Weapon(
        name="手槍",
        en_name="Pistol",
        damage_dice="1d10",
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.AMMUNITION, WeaponProperty.LOADING],
        range_normal=9.0,
        range_long=27.0,
        is_martial=True,
        mastery=WeaponMastery.VEX,
        weight=3.0,
        cost_gp=250.0,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# 護甲資料
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ArmorData:
    """護甲靜態資料。"""

    id: str  # 英文 key
    name: str  # 中文名
    en_name: str
    category: str  # "light" / "medium" / "heavy" / "shield"
    base_ac: int  # 基礎 AC
    dex_cap: int | None = None  # DEX 加值上限（None = 無限, 0 = 不加）
    str_requirement: int = 0  # 力量需求
    stealth_disadvantage: bool = False
    weight: float = 0.0  # 磅
    cost_gp: float = 0.0


ARMOR_REGISTRY: dict[str, ArmorData] = {
    "Padded": ArmorData(
        "Padded", "綿甲", "Padded", "light", 11, None, 0, True, 8, 5,
    ),
    "Leather": ArmorData(
        "Leather", "皮甲", "Leather", "light", 11, None, 0, False, 10, 10,
    ),
    "Studded Leather": ArmorData(
        "Studded Leather", "鑲釘皮甲", "Studded Leather", "light", 12, None, 0, False, 13, 45,
    ),
    "Hide": ArmorData(
        "Hide", "獸皮甲", "Hide", "medium", 12, 2, 0, False, 12, 10,
    ),
    "Chain Shirt": ArmorData(
        "Chain Shirt", "鏈衫", "Chain Shirt", "medium", 13, 2, 0, False, 20, 50,
    ),
    "Scale Mail": ArmorData(
        "Scale Mail", "鱗甲", "Scale Mail", "medium", 14, 2, 0, True, 45, 50,
    ),
    "Breastplate": ArmorData(
        "Breastplate", "胸甲", "Breastplate", "medium", 14, 2, 0, False, 20, 400,
    ),
    "Half Plate": ArmorData(
        "Half Plate", "半身甲", "Half Plate", "medium", 15, 2, 0, True, 40, 750,
    ),
    "Ring Mail": ArmorData(
        "Ring Mail", "環甲", "Ring Mail", "heavy", 14, 0, 0, True, 40, 30,
    ),
    "Chain Mail": ArmorData(
        "Chain Mail", "鏈甲", "Chain Mail", "heavy", 16, 0, 13, True, 55, 75,
    ),
    "Splint": ArmorData(
        "Splint", "鍛鍊甲", "Splint", "heavy", 17, 0, 15, True, 60, 200,
    ),
    "Plate": ArmorData(
        "Plate", "板甲", "Plate", "heavy", 18, 0, 15, True, 65, 1500,
    ),
    "Shield": ArmorData(
        "Shield", "盾牌", "Shield", "shield", 2, None, 0, False, 6, 10,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# 藥水 / 消耗品
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConsumableData:
    """消耗品靜態資料。"""

    id: str
    name: str
    en_name: str
    description: str
    effect_type: str  # "healing" / "buff" / "utility"
    healing_dice: str  # 如 "2d4+2"
    cost_gp: float
    weight: float = 0.5


CONSUMABLE_REGISTRY: dict[str, ConsumableData] = {
    "Potion of Healing": ConsumableData(
        id="Potion of Healing",
        name="治療藥水",
        en_name="Potion of Healing",
        description="飲用恢復 2d4+2 HP。可用附贈動作飲用或對 1.5m 內生物施用。",
        effect_type="healing",
        healing_dice="2d4+2",
        cost_gp=50,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# 裝備包
# ─────────────────────────────────────────────────────────────────────────────

EQUIPMENT_PACKS: dict[str, list[str]] = {
    "Scholar's Pack": [
        "背包", "書本", "墨水", "墨水筆", "油燈", "燈油×10", "羊皮紙×10", "火種盒",
    ],
    "Explorer's Pack": [
        "背包", "睡袋", "燈油×2", "口糧×10", "繩子", "火種盒", "火把×10", "水袋",
    ],
    "Dungeoneer's Pack": [
        "背包", "鐵蒺藜", "撬棍", "燈油×2", "口糧×10", "繩子", "火種盒", "火把×10", "水袋",
    ],
    "Burglar's Pack": [
        "背包", "滾珠", "鈴鐺", "蠟燭×10", "撬棍", "帶罩提燈", "燈油×7", "口糧×5",
        "繩子", "火種盒", "水袋",
    ],
    "Diplomat's Pack": [
        "箱子", "華服", "墨水", "墨水筆×5", "油燈", "地圖盒×2", "燈油×4", "紙×5",
        "羊皮紙×5", "香水", "火種盒",
    ],
    "Entertainer's Pack": [
        "背包", "睡袋", "鈴鐺", "牛眼提燈", "戲服×3", "鏡子", "燈油×8", "口糧×9",
        "火種盒", "水袋",
    ],
    "Priest's Pack": [
        "背包", "毯子", "聖水", "油燈", "口糧×7", "長袍", "火種盒",
    ],
}
