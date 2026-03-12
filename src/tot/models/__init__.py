"""T.O.T. Bone Engine 核心 Pydantic 資料模型。

所有跨模組的資料結構都定義在這裡。Bone Engine 是純確定性的
——不呼叫 LLM、除了骰子以外沒有隨機性。
基於 D&D 2024 (5.5e) 規則。

模組結構：
- enums.py       ← 所有 StrEnum + 常數
- creature.py    ← Character + Monster + Weapon + Item
- spell.py       ← Spell
- map.py         ← Position, Entity, Actor, Prop, Wall, Zone, MapManifest, MapState
- combat_state.py ← TurnState, InitiativeEntry, CombatState, MoveEvent, MoveResult, AoePreview
- exploration.py  ← Pointcrawl 探索系統
"""

from __future__ import annotations

from tot.models.combat_state import (
    AoePreview,
    CombatantRef,
    CombatState,
    InitiativeEntry,
    MoveEvent,
    MoveResult,
    TurnState,
)
from tot.models.creature import (
    AbilityScores,
    ActiveCondition,
    Character,
    DeathSaves,
    Item,
    Monster,
    MonsterAction,
    SpellSlots,
    Weapon,
)
from tot.models.enums import (
    SIZE_ORDER,
    SIZE_RADIUS_M,
    SKILL_ABILITY_MAP,
    Ability,
    AoeShape,
    Condition,
    CoverType,
    CreatureType,
    DamageType,
    EncounterType,
    MapScale,
    NodeType,
    Size,
    Skill,
    SpellAttackType,
    SpellEffectType,
    SpellSchool,
    WeaponMastery,
    WeaponProperty,
)
from tot.models.exploration import (
    DeploymentState,
    EncounterResult,
    ExplorationEdge,
    ExplorationMap,
    ExplorationNode,
    ExplorationState,
    MapStackEntry,
)
from tot.models.map import (
    Actor,
    Entity,
    MapManifest,
    MapState,
    Position,
    Prop,
    Wall,
    Zone,
    ZoneConnection,
)
from tot.models.spell import Spell

__all__ = [
    # enums
    "Ability",
    "AoeShape",
    "Condition",
    "CoverType",
    "CreatureType",
    "DamageType",
    "EncounterType",
    "MapScale",
    "NodeType",
    "SIZE_ORDER",
    "SIZE_RADIUS_M",
    "SKILL_ABILITY_MAP",
    "Size",
    "Skill",
    "SpellAttackType",
    "SpellEffectType",
    "SpellSchool",
    "WeaponMastery",
    "WeaponProperty",
    # creature
    "AbilityScores",
    "ActiveCondition",
    "Character",
    "DeathSaves",
    "Item",
    "Monster",
    "MonsterAction",
    "SpellSlots",
    "Weapon",
    # spell
    "Spell",
    # map
    "Actor",
    "Entity",
    "MapManifest",
    "MapState",
    "Position",
    "Prop",
    "Wall",
    "Zone",
    "ZoneConnection",
    # combat_state
    "AoePreview",
    "CombatantRef",
    "CombatState",
    "InitiativeEntry",
    "MoveEvent",
    "MoveResult",
    "TurnState",
    # exploration
    "DeploymentState",
    "EncounterResult",
    "ExplorationEdge",
    "ExplorationMap",
    "ExplorationNode",
    "ExplorationState",
    "MapStackEntry",
]
