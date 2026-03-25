"""2024 PHB (5.5e) 專長資料：起源專長（建角用）。

資料來源：docs/2024_translate/phb/ch5_feats.md
目前只收錄起源專長（8 個），通用/戰鬥風格/史詩恩賜專長在升級系統時再擴充。
"""

from __future__ import annotations

from dataclasses import dataclass

from tot.models.enums import Skill


@dataclass(frozen=True)
class FeatData:
    """一個 PHB 專長的資料。"""

    id: str  # 英文 key（如 "Alert"）
    name_zh: str
    name_en: str
    category: str  # "起源" / "通用" / "戰鬥風格" / "史詩恩賜"
    description: str  # 完整效果中文說明
    has_spell_choice: bool = False  # 如 Magic Initiate 需要選戲法/法術
    repeatable: bool = False  # 是否可重複選取
    # 技能選位授予：choice_count > 0 時，建角需要讓玩家選技能
    skill_choice_count: int = 0  # 可選幾項技能（0 = 不授予技能）
    skill_choice_pool: tuple[Skill, ...] = ()  # 可選池；空 = 所有 18 項技能


def get_available_class_skills(
    class_skill_list: list[Skill],
    background_skills: list[Skill],
    feat_skills: list[Skill],
) -> list[Skill]:
    """計算職業技能選擇的可用清單。

    Available = ClassList - (BackgroundSkills ∪ FeatSkills)

    Args:
        class_skill_list: 職業可選技能清單。
        background_skills: 背景固定授予的技能。
        feat_skills: 起源專長選位授予的技能。

    Returns:
        過濾後的可用職業技能清單。
    """
    occupied = set(background_skills) | set(feat_skills)
    return [s for s in class_skill_list if s not in occupied]


ORIGIN_FEAT_REGISTRY: dict[str, FeatData] = {
    "Alert": FeatData(
        id="Alert",
        name_zh="警覺",
        name_en="Alert",
        category="起源",
        description=(
            "先攻熟練：擲先攻時加上熟練加值。先攻交換：擲完先攻後，可與一名自願盟友交換先攻順序。"
        ),
    ),
    "Crafter": FeatData(
        id="Crafter",
        name_zh="製作者",
        name_en="Crafter",
        category="起源",
        description=(
            "工具熟練：獲得三種工匠工具的熟練。"
            "折扣：購買非魔法物品享 20% 折扣。"
            "快速製作：長休後可用工具製作一件基本裝備（持續至下次長休）。"
        ),
    ),
    "Healer": FeatData(
        id="Healer",
        name_zh="治療者",
        name_en="Healer",
        category="起源",
        description=(
            "戰場醫護：消耗治療工具包 1 次使用量，運用動作照料生物，"
            "該生物消耗 1 顆生命骰回復 HP + 你的熟練加值。"
            "治療重骰：治療骰到 1 可重骰。"
        ),
    ),
    "Lucky": FeatData(
        id="Lucky",
        name_zh="幸運",
        name_en="Lucky",
        category="起源",
        description=(
            "幸運點數 = 熟練加值，長休恢復。消耗 1 點給自己 d20 檢定優勢，或給敵人攻擊擲骰劣勢。"
        ),
    ),
    "Magic Initiate: Cleric": FeatData(
        id="Magic Initiate: Cleric",
        name_zh="魔法新手：牧師",
        name_en="Magic Initiate: Cleric",
        category="起源",
        description=(
            "學會 2 個牧師戲法和 1 個 1 環牧師法術。"
            "施法屬性為 INT/WIS/CHA 三選一。"
            "1 環法術永備，可免費施放 1 次（長休恢復），也可用法術位施放。"
        ),
        has_spell_choice=True,
    ),
    "Magic Initiate: Druid": FeatData(
        id="Magic Initiate: Druid",
        name_zh="魔法新手：德魯伊",
        name_en="Magic Initiate: Druid",
        category="起源",
        description=(
            "學會 2 個德魯伊戲法和 1 個 1 環德魯伊法術。"
            "施法屬性為 INT/WIS/CHA 三選一。"
            "1 環法術永備，可免費施放 1 次（長休恢復），也可用法術位施放。"
        ),
        has_spell_choice=True,
    ),
    "Magic Initiate: Wizard": FeatData(
        id="Magic Initiate: Wizard",
        name_zh="魔法新手：法師",
        name_en="Magic Initiate: Wizard",
        category="起源",
        description=(
            "學會 2 個法師戲法和 1 個 1 環法師法術。"
            "施法屬性為 INT/WIS/CHA 三選一。"
            "1 環法術永備，可免費施放 1 次（長休恢復），也可用法術位施放。"
        ),
        has_spell_choice=True,
    ),
    "Musician": FeatData(
        id="Musician",
        name_zh="樂師",
        name_en="Musician",
        category="起源",
        description=(
            "樂器訓練：獲得三種樂器的熟練。"
            "鼓舞之歌：短休或長休結束時，演奏樂器，"
            "最多熟練加值數量的盟友獲得英雄靈感。"
        ),
    ),
    "Savage Attacker": FeatData(
        id="Savage Attacker",
        name_zh="野蠻打擊者",
        name_en="Savage Attacker",
        category="起源",
        description="每回合一次，武器命中時可骰兩次傷害骰，擇一使用。",
    ),
    "Skilled": FeatData(
        id="Skilled",
        name_zh="博學",
        name_en="Skilled",
        category="起源",
        description="獲得三項自選技能或工具的熟練。",
        repeatable=True,
        skill_choice_count=3,  # 3 項自選，pool 為空 = 所有技能
    ),
    "Tavern Brawler": FeatData(
        id="Tavern Brawler",
        name_zh="酒館鬥毆者",
        name_en="Tavern Brawler",
        category="起源",
        description=(
            "徒手打擊傷害改為 1d4 + STR 修正值。"
            "傷害骰到 1 可重骰。即興武器熟練。"
            "徒手命中時每回合一次可推擊目標 1.5m。"
        ),
    ),
    "Tough": FeatData(
        id="Tough",
        name_zh="堅韌",
        name_en="Tough",
        category="起源",
        description="最大 HP 增加 = 角色等級 × 2。之後每升 1 級再 +2 HP。",
    ),
}
