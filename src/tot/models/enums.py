"""T.O.T. Bone Engine 列舉型別與常數。"""

from __future__ import annotations

from enum import StrEnum


class Ability(StrEnum):
    STR = "STR"
    DEX = "DEX"
    CON = "CON"
    INT = "INT"
    WIS = "WIS"
    CHA = "CHA"


class Skill(StrEnum):
    # 力量系
    ATHLETICS = "Athletics"
    # 敏捷系
    ACROBATICS = "Acrobatics"
    SLEIGHT_OF_HAND = "Sleight of Hand"
    STEALTH = "Stealth"
    # 智力系
    ARCANA = "Arcana"
    HISTORY = "History"
    INVESTIGATION = "Investigation"
    NATURE = "Nature"
    RELIGION = "Religion"
    # 感知系
    ANIMAL_HANDLING = "Animal Handling"
    INSIGHT = "Insight"
    MEDICINE = "Medicine"
    PERCEPTION = "Perception"
    SURVIVAL = "Survival"
    # 魅力系
    DECEPTION = "Deception"
    INTIMIDATION = "Intimidation"
    PERFORMANCE = "Performance"
    PERSUASION = "Persuasion"


# 技能 → 對應屬性的對照表
SKILL_ABILITY_MAP: dict[Skill, Ability] = {
    Skill.ATHLETICS: Ability.STR,
    Skill.ACROBATICS: Ability.DEX,
    Skill.SLEIGHT_OF_HAND: Ability.DEX,
    Skill.STEALTH: Ability.DEX,
    Skill.ARCANA: Ability.INT,
    Skill.HISTORY: Ability.INT,
    Skill.INVESTIGATION: Ability.INT,
    Skill.NATURE: Ability.INT,
    Skill.RELIGION: Ability.INT,
    Skill.ANIMAL_HANDLING: Ability.WIS,
    Skill.INSIGHT: Ability.WIS,
    Skill.MEDICINE: Ability.WIS,
    Skill.PERCEPTION: Ability.WIS,
    Skill.SURVIVAL: Ability.WIS,
    Skill.DECEPTION: Ability.CHA,
    Skill.INTIMIDATION: Ability.CHA,
    Skill.PERFORMANCE: Ability.CHA,
    Skill.PERSUASION: Ability.CHA,
}


class DamageType(StrEnum):
    ACID = "Acid"
    BLUDGEONING = "Bludgeoning"
    COLD = "Cold"
    FIRE = "Fire"
    FORCE = "Force"
    LIGHTNING = "Lightning"
    NECROTIC = "Necrotic"
    PIERCING = "Piercing"
    POISON = "Poison"
    PSYCHIC = "Psychic"
    RADIANT = "Radiant"
    SLASHING = "Slashing"
    THUNDER = "Thunder"


class Condition(StrEnum):
    BLINDED = "Blinded"
    CHARMED = "Charmed"
    DEAFENED = "Deafened"
    DISENGAGING = "Disengaging"  # 追蹤撤離動作效果（1 輪）
    DODGING = "Dodging"  # 非官方狀態，追蹤閃避動作效果（1 輪）
    EXHAUSTION = "Exhaustion"
    FRIGHTENED = "Frightened"
    GRAPPLED = "Grappled"
    INCAPACITATED = "Incapacitated"
    INVISIBLE = "Invisible"
    PARALYZED = "Paralyzed"
    PETRIFIED = "Petrified"
    POISONED = "Poisoned"
    PRONE = "Prone"
    RESTRAINED = "Restrained"
    STUNNED = "Stunned"
    UNCONSCIOUS = "Unconscious"
    SILENCED = "Silenced"  # Silence 法術範圍內，無法施放 V 成分法術
    WEAKENED = "Weakened"  # 2024 新增，傷害減半


class Size(StrEnum):
    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    HUGE = "Huge"
    GARGANTUAN = "Gargantuan"


# 體型 → 碰撞半徑（公尺），D&D 5e 標準空間佔據的一半
SIZE_RADIUS_M: dict[Size, float] = {
    Size.TINY: 0.15,  # 0.3m 直徑
    Size.SMALL: 0.375,  # 0.75m 直徑（半格）
    Size.MEDIUM: 0.75,  # 1.5m 直徑（1 格）
    Size.LARGE: 1.5,  # 3.0m 直徑（2 格）
    Size.HUGE: 2.25,  # 4.5m 直徑（3 格）
    Size.GARGANTUAN: 3.0,  # 6.0m 直徑（4 格）
}

# 體型序號，用於穿越規則比較（差 ≥ 2 級可穿越敵對）
SIZE_ORDER: dict[Size, int] = {
    Size.TINY: 0,
    Size.SMALL: 1,
    Size.MEDIUM: 2,
    Size.LARGE: 3,
    Size.HUGE: 4,
    Size.GARGANTUAN: 5,
}


class CreatureType(StrEnum):
    ABERRATION = "Aberration"
    BEAST = "Beast"
    CELESTIAL = "Celestial"
    CONSTRUCT = "Construct"
    DRAGON = "Dragon"
    ELEMENTAL = "Elemental"
    FEY = "Fey"
    FIEND = "Fiend"
    GIANT = "Giant"
    HUMANOID = "Humanoid"
    MONSTROSITY = "Monstrosity"
    OOZE = "Ooze"
    PLANT = "Plant"
    UNDEAD = "Undead"


class SpellSchool(StrEnum):
    ABJURATION = "Abjuration"
    CONJURATION = "Conjuration"
    DIVINATION = "Divination"
    ENCHANTMENT = "Enchantment"
    EVOCATION = "Evocation"
    ILLUSION = "Illusion"
    NECROMANCY = "Necromancy"
    TRANSMUTATION = "Transmutation"


class CoverType(StrEnum):
    """掩蔽類型。"""

    NONE = "None"
    HALF = "Half"  # +2 AC 與 DEX 豁免
    THREE_QUARTERS = "Three-Quarters"  # +5 AC 與 DEX 豁免
    TOTAL = "Total"  # 無法被直接攻擊


class WeaponMastery(StrEnum):
    """2024 武器專精效果。"""

    CLEAVE = "Cleave"  # 命中後對相鄰另一目標造成屬性修正傷害
    GRAZE = "Graze"  # 未命中仍造成屬性修正傷害
    NICK = "Nick"  # 額外附贈動作攻擊
    PUSH = "Push"  # 命中後推開目標 3m
    SAP = "Sap"  # 命中後目標下次攻擊劣勢
    SLOW = "Slow"  # 命中後減速 3m
    TOPPLE = "Topple"  # 命中後目標 CON 豁免，失敗倒地
    VEX = "Vex"  # 命中後下次攻擊同目標優勢


class SpellAttackType(StrEnum):
    """法術攻擊類型。"""

    NONE = "none"  # 無攻擊擲骰（豁免型或自動命中）
    MELEE = "melee"  # 近戰法術攻擊
    RANGED = "ranged"  # 遠程法術攻擊


class SpellEffectType(StrEnum):
    """法術主要效果類型。"""

    DAMAGE = "damage"
    HEALING = "healing"
    CONDITION = "condition"  # 純施加狀態
    BUFF = "buff"  # 增益效果
    UTILITY = "utility"  # 非戰鬥用途


class AoeShape(StrEnum):
    """AoE 形狀。"""

    SPHERE = "sphere"  # 球形（2D 平面 = 圓形），如火球術
    CONE = "cone"  # 錐形，如燃燒之手
    LINE = "line"  # 線形，如閃電束
    CUBE = "cube"  # 方形，如雷鳴波


class ShapeType(StrEnum):
    """BoundingShape 幾何形狀類型。"""

    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    CONE = "cone"
    LINE = "line"
    CYLINDER = "cylinder"


class Material(StrEnum):
    """D&D 2024 DMG 物件材質。"""

    CLOTH = "Cloth"
    PAPER = "Paper"
    ROPE = "Rope"
    CRYSTAL = "Crystal"
    GLASS = "Glass"
    ICE = "Ice"
    WOOD = "Wood"
    BONE = "Bone"
    STONE = "Stone"
    IRON = "Iron"
    STEEL = "Steel"
    MITHRAL = "Mithral"
    ADAMANTINE = "Adamantine"


class Fragility(StrEnum):
    """物件堅固程度（影響 HP 倍率）。"""

    FRAGILE = "Fragile"  # ×1
    RESILIENT = "Resilient"  # ×2


class SurfaceTrigger(StrEnum):
    """SurfaceEffect 觸發時機。"""

    ENTER = "enter"  # 進入時
    STAY = "stay"  # 回合開始仍在範圍內
    LEAVE = "leave"  # 離開時


class TileType(StrEnum):
    """地格類型。"""

    FLOOR = "floor"
    WALL = "wall"


# 材質 → AC（D&D 2024 DMG）
MATERIAL_AC: dict[Material, int] = {
    Material.CLOTH: 11,
    Material.PAPER: 11,
    Material.ROPE: 11,
    Material.CRYSTAL: 13,
    Material.GLASS: 13,
    Material.ICE: 13,
    Material.WOOD: 15,
    Material.BONE: 15,
    Material.STONE: 17,
    Material.IRON: 19,
    Material.STEEL: 19,
    Material.MITHRAL: 21,
    Material.ADAMANTINE: 23,
}

# 堅固程度 → HP 倍率
FRAGILITY_HP_MULTIPLIER: dict[Fragility, int] = {
    Fragility.FRAGILE: 1,
    Fragility.RESILIENT: 3,
}

# 體型 → 物件 HP 骰（D&D 2024 DMG）
OBJECT_HP_DICE: dict[Size, str] = {
    Size.TINY: "1d4",
    Size.SMALL: "1d6",
    Size.MEDIUM: "1d8",
    Size.LARGE: "2d6",
    Size.HUGE: "3d6",
    Size.GARGANTUAN: "5d6",
}


class WeaponProperty(StrEnum):
    AMMUNITION = "Ammunition"
    FINESSE = "Finesse"
    HEAVY = "Heavy"
    LIGHT = "Light"
    LOADING = "Loading"
    REACH = "Reach"
    THROWN = "Thrown"
    TWO_HANDED = "Two-Handed"
    VERSATILE = "Versatile"


class NodeType(StrEnum):
    """探索節點類型。"""

    ROOM = "room"  # 地城房間
    CORRIDOR = "corridor"  # 走廊
    POI = "poi"  # 城鎮興趣點
    TOWN = "town"  # 城鎮（世界圖層）
    DUNGEON = "dungeon"  # 地城入口（世界圖層）
    LANDMARK = "landmark"  # 自然地標


class MapScale(StrEnum):
    """探索地圖尺度，決定時間單位。"""

    DUNGEON = "dungeon"  # 分鐘
    TOWN = "town"  # 小時
    WORLD = "world"  # 天


class EncounterType(StrEnum):
    """遭遇類型。"""

    SURPRISE = "surprise"  # 玩家偷襲成功 → 擴大佈陣區 + 敵人劣勢先攻
    NORMAL = "normal"  # 正常遭遇 → 標準佈陣區
    AMBUSH = "ambush"  # 敵人伏擊 → 跳過佈陣，玩家劣勢先攻


class ToolCategory(StrEnum):
    """工具類別。"""

    ARTISAN = "artisan"
    GAMING = "gaming"
    MUSICAL = "musical"
    OTHER = "other"


class Tool(StrEnum):
    """D&D 2024 工具熟練。"""

    # 工匠工具（17 種）
    ALCHEMIST_SUPPLIES = "Alchemist's Supplies"
    BREWER_SUPPLIES = "Brewer's Supplies"
    CALLIGRAPHER_SUPPLIES = "Calligrapher's Supplies"
    CARPENTER_TOOLS = "Carpenter's Tools"
    CARTOGRAPHER_TOOLS = "Cartographer's Tools"
    COBBLER_TOOLS = "Cobbler's Tools"
    COOK_UTENSILS = "Cook's Utensils"
    GLASSBLOWER_TOOLS = "Glassblower's Tools"
    JEWELER_TOOLS = "Jeweler's Tools"
    LEATHERWORKER_TOOLS = "Leatherworker's Tools"
    MASON_TOOLS = "Mason's Tools"
    PAINTER_SUPPLIES = "Painter's Supplies"
    POTTER_TOOLS = "Potter's Tools"
    SMITH_TOOLS = "Smith's Tools"
    TINKER_TOOLS = "Tinker's Tools"
    WEAVER_TOOLS = "Weaver's Tools"
    WOODCARVER_TOOLS = "Woodcarver's Tools"
    # 遊戲組（4 種）
    DICE_SET = "Dice Set"
    DRAGONCHESS_SET = "Dragonchess Set"
    PLAYING_CARDS = "Playing Cards"
    THREE_DRAGON_ANTE = "Three-Dragon Ante Set"
    # 樂器（10 種）
    BAGPIPES = "Bagpipes"
    DRUM = "Drum"
    DULCIMER = "Dulcimer"
    FLUTE = "Flute"
    HORN = "Horn"
    LUTE = "Lute"
    LYRE = "Lyre"
    PAN_FLUTE = "Pan Flute"
    SHAWM = "Shawm"
    VIOL = "Viol"
    # 其他（6 種）
    DISGUISE_KIT = "Disguise Kit"
    FORGERY_KIT = "Forgery Kit"
    HERBALISM_KIT = "Herbalism Kit"
    NAVIGATOR_TOOLS = "Navigator's Tools"
    POISONER_KIT = "Poisoner's Kit"
    THIEVES_TOOLS = "Thieves' Tools"


# 工具類別對應表
TOOL_CATEGORY_MAP: dict[Tool, ToolCategory] = {
    # 工匠工具
    Tool.ALCHEMIST_SUPPLIES: ToolCategory.ARTISAN,
    Tool.BREWER_SUPPLIES: ToolCategory.ARTISAN,
    Tool.CALLIGRAPHER_SUPPLIES: ToolCategory.ARTISAN,
    Tool.CARPENTER_TOOLS: ToolCategory.ARTISAN,
    Tool.CARTOGRAPHER_TOOLS: ToolCategory.ARTISAN,
    Tool.COBBLER_TOOLS: ToolCategory.ARTISAN,
    Tool.COOK_UTENSILS: ToolCategory.ARTISAN,
    Tool.GLASSBLOWER_TOOLS: ToolCategory.ARTISAN,
    Tool.JEWELER_TOOLS: ToolCategory.ARTISAN,
    Tool.LEATHERWORKER_TOOLS: ToolCategory.ARTISAN,
    Tool.MASON_TOOLS: ToolCategory.ARTISAN,
    Tool.PAINTER_SUPPLIES: ToolCategory.ARTISAN,
    Tool.POTTER_TOOLS: ToolCategory.ARTISAN,
    Tool.SMITH_TOOLS: ToolCategory.ARTISAN,
    Tool.TINKER_TOOLS: ToolCategory.ARTISAN,
    Tool.WEAVER_TOOLS: ToolCategory.ARTISAN,
    Tool.WOODCARVER_TOOLS: ToolCategory.ARTISAN,
    # 遊戲組
    Tool.DICE_SET: ToolCategory.GAMING,
    Tool.DRAGONCHESS_SET: ToolCategory.GAMING,
    Tool.PLAYING_CARDS: ToolCategory.GAMING,
    Tool.THREE_DRAGON_ANTE: ToolCategory.GAMING,
    # 樂器
    Tool.BAGPIPES: ToolCategory.MUSICAL,
    Tool.DRUM: ToolCategory.MUSICAL,
    Tool.DULCIMER: ToolCategory.MUSICAL,
    Tool.FLUTE: ToolCategory.MUSICAL,
    Tool.HORN: ToolCategory.MUSICAL,
    Tool.LUTE: ToolCategory.MUSICAL,
    Tool.LYRE: ToolCategory.MUSICAL,
    Tool.PAN_FLUTE: ToolCategory.MUSICAL,
    Tool.SHAWM: ToolCategory.MUSICAL,
    Tool.VIOL: ToolCategory.MUSICAL,
    # 其他
    Tool.DISGUISE_KIT: ToolCategory.OTHER,
    Tool.FORGERY_KIT: ToolCategory.OTHER,
    Tool.HERBALISM_KIT: ToolCategory.OTHER,
    Tool.NAVIGATOR_TOOLS: ToolCategory.OTHER,
    Tool.POISONER_KIT: ToolCategory.OTHER,
    Tool.THIEVES_TOOLS: ToolCategory.OTHER,
}
