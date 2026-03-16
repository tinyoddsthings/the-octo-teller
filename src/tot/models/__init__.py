"""T.O.T. Bone Engine 核心 Pydantic 資料模型。

所有跨模組的資料結構都定義在這裡。Bone Engine 是純確定性的
——不呼叫 LLM、除了骰子以外沒有隨機性。
基於 D&D 2024 (5.5e) 規則。

模組結構：
- enums.py       ← 所有 StrEnum + 常數
- shapes.py      ← BoundingShape 幾何碰撞形狀
- creature.py    ← Character + Monster + Weapon + Item
- spell.py       ← Spell
- map.py         ← Position, Entity, Actor, Prop, Wall, Zone, SurfaceEffect,
                   CoverResult, MapManifest, MapState
- combat_state.py ← TurnState, InitiativeEntry, CombatState, MoveEvent, MoveResult, AoePreview
- exploration.py  ← Pointcrawl 探索系統
- adventure.py   ← 固定劇本冒險系統
"""

from __future__ import annotations

from tot.models.adventure import (
    AdventureScript,
    AdventureState,
    DialogueLine,
    EncounterDef,
    EnemyDef,
    EventAction,
    EventTrigger,
    NpcDef,
    RewardDef,
    ScriptEvent,
)
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
    Combatant,
    DeathSaves,
    Item,
    Monster,
    MonsterAction,
    SpellSlots,
    Weapon,
)
from tot.models.enums import (
    FRAGILITY_HP_MULTIPLIER,
    MATERIAL_AC,
    OBJECT_HP_DICE,
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
    Fragility,
    MapScale,
    Material,
    NodeType,
    ShapeType,
    Size,
    Skill,
    SpellAttackType,
    SpellEffectType,
    SpellSchool,
    SurfaceTrigger,
    TileType,
    WeaponMastery,
    WeaponProperty,
)
from tot.models.exploration import (
    AreaExploreState,
    DeploymentState,
    EncounterResult,
    ExplorationEdge,
    ExplorationMap,
    ExplorationNode,
    ExplorationState,
    MapStackEntry,
    NodeItem,
)
from tot.models.map import (
    Actor,
    CoverResult,
    Entity,
    LootEntry,
    MapManifest,
    MapState,
    Position,
    Prop,
    SurfaceEffect,
    Wall,
    Zone,
    ZoneConnection,
)
from tot.models.shapes import BoundingShape
from tot.models.spell import Spell, SpellAoe, SpellComponents, SpellUpcast
from tot.models.time import GameClock, format_seconds_human

__all__ = [
    # enums
    "Ability",
    "AoeShape",
    "Condition",
    "CoverType",
    "CreatureType",
    "DamageType",
    "EncounterType",
    "FRAGILITY_HP_MULTIPLIER",
    "Fragility",
    "MATERIAL_AC",
    "MapScale",
    "Material",
    "NodeType",
    "OBJECT_HP_DICE",
    "SIZE_ORDER",
    "SIZE_RADIUS_M",
    "SKILL_ABILITY_MAP",
    "ShapeType",
    "Size",
    "Skill",
    "SpellAttackType",
    "SpellEffectType",
    "SpellSchool",
    "SurfaceTrigger",
    "TileType",
    "WeaponMastery",
    "WeaponProperty",
    # shapes
    "BoundingShape",
    # creature
    "AbilityScores",
    "ActiveCondition",
    "Character",
    "Combatant",
    "DeathSaves",
    "Item",
    "Monster",
    "MonsterAction",
    "SpellSlots",
    "Weapon",
    # spell
    "Spell",
    "SpellAoe",
    "SpellComponents",
    "SpellUpcast",
    # map
    "Actor",
    "CoverResult",
    "Entity",
    "LootEntry",
    "MapManifest",
    "MapState",
    "Position",
    "Prop",
    "SurfaceEffect",
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
    # time
    "GameClock",
    "format_seconds_human",
    # adventure
    "AdventureScript",
    "AdventureState",
    "DialogueLine",
    "EncounterDef",
    "EnemyDef",
    "EventAction",
    "EventTrigger",
    "NpcDef",
    "RewardDef",
    "ScriptEvent",
    # exploration
    "AreaExploreState",
    "DeploymentState",
    "EncounterResult",
    "ExplorationEdge",
    "ExplorationMap",
    "ExplorationNode",
    "ExplorationState",
    "MapStackEntry",
    "NodeItem",
]
