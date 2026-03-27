"""SourcePack 能力包系統 — 追蹤角色能力的來源和消耗規則。

角色 = 多個 SourcePack 的組合。每個 Pack 來自一個來源
（種族、背景、職業、專長、祈喚等），包含技能、法術、工具等授予。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from tot.models.enums import Ability, Skill, Tool

# ── 列舉 ──────────────────────────────────────────────────────────────────────


class PackType(StrEnum):
    """能力包的來源類型。"""

    SPECIES = "species"
    BACKGROUND = "background"
    CLASS = "class"
    SUBCLASS = "subclass"
    FEAT = "feat"
    INVOCATION = "invocation"


class ProficiencyLevel(StrEnum):
    """技能熟練等級。"""

    NONE = "none"
    PROFICIENT = "proficient"
    EXPERTISE = "expertise"


class SpellCastingType(StrEnum):
    """法術的獲取/施放方式。"""

    KNOWN = "known"  # 職業已知（Warlock/Sorcerer/Bard/Ranger）
    PREPARED = "prepared"  # 職業備妥（Cleric/Druid/Paladin/Wizard）
    INNATE = "innate"  # 種族天賦（Tiefling/Elf/Gnome/Aasimar）
    FEAT = "feat"  # 專長法術（Magic Initiate）
    SPELLBOOK = "spellbook"  # 法術書（Wizard 限定）
    TOME = "tome"  # 契約之書（戲法+儀式）
    INVOCATION = "invocation"  # 祈喚免費（暗影之甲等）


# ── 授予項目 ──────────────────────────────────────────────────────────────────


@dataclass
class SkillGrant:
    """一項技能授予。"""

    skill: Skill
    level: ProficiencyLevel = ProficiencyLevel.PROFICIENT


@dataclass
class SpellGrant:
    """一項法術授予。追蹤來源和消耗規則。

    Attributes:
        en_name: 法術英文名（與 spells.json 的 en_name 對應）。
        casting_type: 獲取/施放方式。
        spellcasting_ability: 施法屬性。None = 用職業預設。
        counts_as_class_spell: 是否算作職業法術（可被祈喚/職業特性加持）。
        free_uses_max: 免費施放次數上限（0 = 不適用，如戲法無限）。
        free_uses_current: 當前剩餘免費次數。
        is_always_prepared: 永備（不計入備妥上限）。
        can_ritual_cast: 可儀式施放（不消耗法術位）。
        can_also_use_slot: 免費用完後可否用法術位施放。
    """

    en_name: str
    casting_type: SpellCastingType
    spellcasting_ability: Ability | None = None
    counts_as_class_spell: bool = False
    free_uses_max: int = 0
    free_uses_current: int = 0
    is_always_prepared: bool = False
    can_ritual_cast: bool = False
    can_also_use_slot: bool = False


@dataclass
class ToolGrant:
    """一項工具授予。"""

    tool: Tool


# ── SourcePack ────────────────────────────────────────────────────────────────


@dataclass
class SourcePack:
    """一個來源的能力包。角色 = 多個 SourcePack 的組合。

    Attributes:
        pack_type: 來源類型（species/background/class/feat/invocation）。
        source_name: 中文名（如「提夫林（煉獄）」「騙徒」「契術師」）。
        source_id: 英文 ID（如「Tiefling:infernal」「Charlatan」「Warlock」）。
        skills: 技能授予列表。
        spells: 法術授予列表。
        tools: 工具授予列表。
        saving_throws: 豁免熟練（通常來自職業）。
    """

    pack_type: PackType
    source_name: str
    source_id: str = ""
    skills: list[SkillGrant] = field(default_factory=list)
    spells: list[SpellGrant] = field(default_factory=list)
    tools: list[ToolGrant] = field(default_factory=list)
    saving_throws: list[Ability] = field(default_factory=list)
    # 未來擴充：
    # resistances: list[DamageType] = field(default_factory=list)
    # features: list[str] = field(default_factory=list)
    # languages: list[str] = field(default_factory=list)
