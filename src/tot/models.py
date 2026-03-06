"""Core Pydantic data models for T.O.T. Bone Engine.

All cross-module data structures live here. The Bone Engine is purely
deterministic — no LLM calls, no randomness beyond dice rolls.
Based on D&D 2024 (5.5e) rules.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Ability(StrEnum):
    STR = "STR"
    DEX = "DEX"
    CON = "CON"
    INT = "INT"
    WIS = "WIS"
    CHA = "CHA"


class Skill(StrEnum):
    # STR
    ATHLETICS = "Athletics"
    # DEX
    ACROBATICS = "Acrobatics"
    SLEIGHT_OF_HAND = "Sleight of Hand"
    STEALTH = "Stealth"
    # INT
    ARCANA = "Arcana"
    HISTORY = "History"
    INVESTIGATION = "Investigation"
    NATURE = "Nature"
    RELIGION = "Religion"
    # WIS
    ANIMAL_HANDLING = "Animal Handling"
    INSIGHT = "Insight"
    MEDICINE = "Medicine"
    PERCEPTION = "Perception"
    SURVIVAL = "Survival"
    # CHA
    DECEPTION = "Deception"
    INTIMIDATION = "Intimidation"
    PERFORMANCE = "Performance"
    PERSUASION = "Persuasion"


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


class Size(StrEnum):
    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    HUGE = "Huge"
    GARGANTUAN = "Gargantuan"


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


# ---------------------------------------------------------------------------
# Ability Scores
# ---------------------------------------------------------------------------

class AbilityScores(BaseModel):
    """Six ability scores with auto-computed modifiers."""

    STR: int = 10
    DEX: int = 10
    CON: int = 10
    INT: int = 10
    WIS: int = 10
    CHA: int = 10

    def score(self, ability: Ability) -> int:
        return getattr(self, ability.value)

    def modifier(self, ability: Ability) -> int:
        """(score - 10) // 2, per PHB."""
        return (self.score(ability) - 10) // 2


# ---------------------------------------------------------------------------
# Active Condition (runtime state)
# ---------------------------------------------------------------------------

class ActiveCondition(BaseModel):
    """A condition currently affecting a creature."""

    condition: Condition
    source: str = ""
    remaining_rounds: int | None = None  # None = indefinite / until removed
    exhaustion_level: int = 0  # only for Exhaustion (1-6)


# ---------------------------------------------------------------------------
# Spell
# ---------------------------------------------------------------------------

class Spell(BaseModel):
    name: str
    level: int = Field(ge=0, le=9)  # 0 = cantrip
    school: SpellSchool
    casting_time: str = "1 action"
    range: str = "Self"
    duration: str = "Instantaneous"
    concentration: bool = False
    ritual: bool = False
    description: str = ""
    damage_dice: str = ""  # e.g. "1d10", "" if no damage
    damage_type: DamageType | None = None
    save_ability: Ability | None = None  # for save-based spells
    classes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Item & Weapon
# ---------------------------------------------------------------------------

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


class Weapon(BaseModel):
    name: str
    damage_dice: str  # e.g. "1d8"
    damage_type: DamageType
    properties: list[WeaponProperty] = Field(default_factory=list)
    range_normal: int = 1  # metres; 1 = melee
    range_long: int | None = None  # for ranged/thrown
    is_martial: bool = False

    @computed_field
    @property
    def is_ranged(self) -> bool:
        return self.range_normal > 1

    @computed_field
    @property
    def is_finesse(self) -> bool:
        return WeaponProperty.FINESSE in self.properties


class Item(BaseModel):
    name: str
    description: str = ""
    weight: float = 0.0  # kg
    quantity: int = 1
    is_magic: bool = False
    requires_attunement: bool = False


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------

class SpellSlots(BaseModel):
    """Tracks current / max spell slots per level."""

    max_slots: dict[int, int] = Field(default_factory=dict)  # {1: 4, 2: 3, ...}
    current_slots: dict[int, int] = Field(default_factory=dict)

    def use(self, level: int) -> bool:
        current = self.current_slots.get(level, 0)
        if current <= 0:
            return False
        self.current_slots[level] = current - 1
        return True

    def recover_all(self) -> None:
        self.current_slots = dict(self.max_slots)


class DeathSaves(BaseModel):
    successes: int = Field(default=0, ge=0, le=3)
    failures: int = Field(default=0, ge=0, le=3)

    def reset(self) -> None:
        self.successes = 0
        self.failures = 0

    @computed_field
    @property
    def is_stable(self) -> bool:
        return self.successes >= 3

    @computed_field
    @property
    def is_dead(self) -> bool:
        return self.failures >= 3


class Character(BaseModel):
    """A player character or NPC companion."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    species: str = ""  # 2024 PHB uses "species" not "race"
    char_class: str = ""
    subclass: str = ""
    level: int = Field(default=1, ge=1, le=20)
    background: str = ""

    ability_scores: AbilityScores = Field(default_factory=AbilityScores)
    proficiency_bonus: int = 2  # derived from level, but stored for convenience

    hp_max: int = 10
    hp_current: int = 10
    hp_temp: int = 0
    hit_dice_total: int = 1
    hit_dice_remaining: int = 1
    hit_die_size: int = 8  # d6/d8/d10/d12

    ac: int = 10
    speed: int = 9  # metres (30ft = ~9m)
    initiative_bonus: int = 0

    skill_proficiencies: list[Skill] = Field(default_factory=list)
    skill_expertise: list[Skill] = Field(default_factory=list)
    saving_throw_proficiencies: list[Ability] = Field(default_factory=list)

    spell_slots: SpellSlots = Field(default_factory=SpellSlots)
    spells_known: list[str] = Field(default_factory=list)
    spells_prepared: list[str] = Field(default_factory=list)
    concentration_spell: str | None = None

    weapons: list[Weapon] = Field(default_factory=list)
    inventory: list[Item] = Field(default_factory=list)

    conditions: list[ActiveCondition] = Field(default_factory=list)
    death_saves: DeathSaves = Field(default_factory=DeathSaves)
    exhaustion_level: int = Field(default=0, ge=0, le=6)

    xp: int = 0

    def ability_modifier(self, ability: Ability) -> int:
        return self.ability_scores.modifier(ability)

    def skill_bonus(self, skill: Skill) -> int:
        ability = SKILL_ABILITY_MAP[skill]
        bonus = self.ability_modifier(ability)
        if skill in self.skill_expertise:
            bonus += self.proficiency_bonus * 2
        elif skill in self.skill_proficiencies:
            bonus += self.proficiency_bonus
        return bonus

    def saving_throw(self, ability: Ability) -> int:
        bonus = self.ability_modifier(ability)
        if ability in self.saving_throw_proficiencies:
            bonus += self.proficiency_bonus
        return bonus

    @computed_field
    @property
    def passive_perception(self) -> int:
        return 10 + self.skill_bonus(Skill.PERCEPTION)

    @computed_field
    @property
    def is_alive(self) -> bool:
        return not self.death_saves.is_dead and self.exhaustion_level < 6

    @computed_field
    @property
    def is_conscious(self) -> bool:
        return self.hp_current > 0

    def has_condition(self, condition: Condition) -> bool:
        return any(c.condition == condition for c in self.conditions)


# ---------------------------------------------------------------------------
# Monster
# ---------------------------------------------------------------------------

class MonsterAction(BaseModel):
    name: str
    attack_bonus: int | None = None  # None = no attack roll (save-based)
    damage_dice: str = ""
    damage_type: DamageType | None = None
    reach: int = 1  # metres
    description: str = ""
    save_dc: int | None = None
    save_ability: Ability | None = None


class Monster(BaseModel):
    """A monster stat block."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    size: Size = Size.MEDIUM
    creature_type: CreatureType = CreatureType.HUMANOID
    alignment: str = ""

    ac: int = 10
    hp_max: int = 10
    hp_current: int = 10
    speed: int = 9

    ability_scores: AbilityScores = Field(default_factory=AbilityScores)
    challenge_rating: float = 0
    xp_reward: int = 0
    proficiency_bonus: int = 2

    damage_resistances: list[DamageType] = Field(default_factory=list)
    damage_immunities: list[DamageType] = Field(default_factory=list)
    condition_immunities: list[Condition] = Field(default_factory=list)

    actions: list[MonsterAction] = Field(default_factory=list)
    conditions: list[ActiveCondition] = Field(default_factory=list)

    # display label for combat (e.g. "Goblin A")
    label: str = ""

    def ability_modifier(self, ability: Ability) -> int:
        return self.ability_scores.modifier(ability)

    @computed_field
    @property
    def is_alive(self) -> bool:
        return self.hp_current > 0

    @computed_field
    @property
    def hp_description(self) -> str:
        """HP description visible to players (not exact numbers)."""
        if self.hp_max == 0:
            return "N/A"
        ratio = self.hp_current / self.hp_max
        if ratio >= 1.0:
            return "Uninjured"
        if ratio >= 0.75:
            return "Lightly wounded"
        if ratio >= 0.50:
            return "Visibly wounded"
        if ratio >= 0.25:
            return "Badly wounded"
        if ratio > 0:
            return "Near death"
        return "Down"

    def has_condition(self, condition: Condition) -> bool:
        if condition in self.condition_immunities:
            return False
        return any(c.condition == condition for c in self.conditions)


# ---------------------------------------------------------------------------
# Combat State
# ---------------------------------------------------------------------------

CombatantRef = tuple[Literal["character", "monster"], UUID]


class InitiativeEntry(BaseModel):
    combatant_type: Literal["character", "monster"]
    combatant_id: UUID
    initiative: int
    is_surprised: bool = False


class CombatState(BaseModel):
    """Tracks the state of an ongoing combat encounter."""

    round_number: int = 1
    current_turn_index: int = 0
    initiative_order: list[InitiativeEntry] = Field(default_factory=list)
    is_active: bool = False
