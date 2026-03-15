"""Demo 場景初始化——3 PC vs 蟲巢首領 + 2 大地精，tutorial_room 地圖。

玩家只操控陶德（Wizard），Aldric/Branwen 由 AI 接管。
角色/怪物以幾何標記（圓形/菱形）渲染於 Braille 地圖上。
總 XP 400（調整後 600），Medium-Hard 遭遇。
"""

from __future__ import annotations

from tot.data.loader import load_map_manifest
from tot.gremlins.bone_engine.combat import start_combat
from tot.models import (
    Ability,
    AbilityScores,
    Actor,
    Character,
    CombatState,
    DamageType,
    MapState,
    Monster,
    MonsterAction,
    Size,
    Skill,
    SpellSlots,
    Weapon,
    WeaponProperty,
)


def create_demo_scene() -> tuple[list[Character], list[Monster], MapState, CombatState]:
    """建立 demo 戰鬥場景。

    回傳 (characters, monsters, map_state, combat_state)。
    """
    # --- 3 個 PC ---
    fighter = Character(
        name="Aldric",
        char_class="Fighter",
        level=5,
        ability_scores=AbilityScores(STR=16, DEX=12, CON=14, INT=10, WIS=12, CHA=8),
        proficiency_bonus=3,
        hp_max=44,
        hp_current=44,
        hit_dice_total=5,
        hit_dice_remaining=5,
        hit_die_size=10,
        ac=18,
        speed=9,
        skill_proficiencies=[Skill.ATHLETICS, Skill.PERCEPTION],
        saving_throw_proficiencies=[Ability.STR, Ability.CON],
        weapons=[
            Weapon(
                name="長劍",
                damage_dice="1d8",
                damage_type=DamageType.SLASHING,
                properties=[WeaponProperty.VERSATILE],
                is_martial=True,
            ),
        ],
        is_ai_controlled=True,
    )

    cleric = Character(
        name="Branwen",
        char_class="Cleric",
        level=5,
        ability_scores=AbilityScores(STR=14, DEX=10, CON=14, INT=10, WIS=18, CHA=12),
        proficiency_bonus=3,
        hp_max=38,
        hp_current=38,
        hit_dice_total=5,
        hit_dice_remaining=5,
        hit_die_size=8,
        ac=18,
        speed=9,
        skill_proficiencies=[Skill.MEDICINE, Skill.RELIGION],
        saving_throw_proficiencies=[Ability.WIS, Ability.CHA],
        weapons=[
            Weapon(
                name="戰錘",
                damage_dice="1d8",
                damage_type=DamageType.BLUDGEONING,
                properties=[],
                is_martial=False,
            ),
        ],
        spell_dc=15,  # 8 + 3 熟練 + 4 WIS
        spell_attack=7,  # 3 熟練 + 4 WIS
        spell_slots=SpellSlots(
            max_slots={1: 4, 2: 3, 3: 2},
            current_slots={1: 4, 2: 3, 3: 2},
        ),
        spells_prepared=["神聖火焰", "療傷術", "祝福術"],
        is_ai_controlled=True,
    )

    wizard = Character(
        name="陶德",
        char_class="Wizard",
        level=5,
        ability_scores=AbilityScores(STR=8, DEX=14, CON=12, INT=18, WIS=12, CHA=10),
        proficiency_bonus=3,
        hp_max=27,
        hp_current=27,
        hit_dice_total=5,
        hit_dice_remaining=5,
        hit_die_size=6,
        ac=15,
        speed=9,
        skill_proficiencies=[Skill.ARCANA, Skill.INVESTIGATION],
        saving_throw_proficiencies=[Ability.INT, Ability.WIS],
        weapons=[
            Weapon(
                name="匕首",
                damage_dice="1d4",
                damage_type=DamageType.PIERCING,
                properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.THROWN],
                range_normal=1,
                range_long=18,
            ),
        ],
        spell_dc=15,  # 8 + 3 熟練 + 4 INT
        spell_attack=7,  # 3 熟練 + 4 INT
        spell_slots=SpellSlots(
            max_slots={1: 4, 2: 3, 3: 2},
            current_slots={1: 4, 2: 3, 3: 2},
        ),
        spells_prepared=["火焰箭", "魔法飛彈", "護盾術", "火球術"],
        spells_known=["火焰箭", "魔法飛彈", "護盾術", "火球術", "法師護甲"],
        is_ai_controlled=False,
    )

    characters = [fighter, cleric, wizard]

    # --- 蟲巢首領 + 2 大地精 ---
    bugbear = Monster(
        name="蟲巢首領",
        label="蟲巢首領",
        size=Size.MEDIUM,
        creature_type="Humanoid",
        ac=16,
        hp_max=27,
        hp_current=27,
        speed=9,
        ability_scores=AbilityScores(STR=15, DEX=14, CON=13, INT=8, WIS=11, CHA=9),
        proficiency_bonus=2,
        challenge_rating=1,
        xp_reward=200,
        actions=[
            MonsterAction(
                name="晨星",
                attack_bonus=4,
                damage_dice="2d8",
                damage_type=DamageType.PIERCING,
                reach=1,
            ),
        ],
    )

    hobgoblin1 = Monster(
        name="大地精",
        label="大地精1",
        size=Size.MEDIUM,
        creature_type="Humanoid",
        ac=18,
        hp_max=11,
        hp_current=11,
        speed=9,
        ability_scores=AbilityScores(STR=13, DEX=12, CON=12, INT=10, WIS=10, CHA=9),
        proficiency_bonus=2,
        challenge_rating=0.5,
        xp_reward=100,
        actions=[
            MonsterAction(
                name="長劍",
                attack_bonus=3,
                damage_dice="1d8",
                damage_type=DamageType.SLASHING,
                reach=1,
            ),
        ],
    )

    hobgoblin2 = Monster(
        name="大地精",
        label="大地精2",
        size=Size.MEDIUM,
        creature_type="Humanoid",
        ac=18,
        hp_max=11,
        hp_current=11,
        speed=9,
        ability_scores=AbilityScores(STR=13, DEX=12, CON=12, INT=10, WIS=10, CHA=9),
        proficiency_bonus=2,
        challenge_rating=0.5,
        xp_reward=100,
        actions=[
            MonsterAction(
                name="長劍",
                attack_bonus=3,
                damage_dice="1d8",
                damage_type=DamageType.SLASHING,
                reach=1,
            ),
        ],
    )

    monsters = [bugbear, hobgoblin1, hobgoblin2]

    # --- 載入地圖、放置 Actor ---
    map_state = load_map_manifest(name="tutorial_room")
    spawns_pc = map_state.manifest.spawn_points.get("players", [])
    spawns_enemy = map_state.manifest.spawn_points.get("enemies", [])

    for idx, char in enumerate(characters):
        pos = spawns_pc[idx] if idx < len(spawns_pc) else spawns_pc[-1]
        map_state.actors.append(
            Actor(
                id=str(char.id),
                combatant_id=char.id,
                combatant_type="character",
                x=pos.x,
                y=pos.y,
                name=char.name,
            )
        )

    for idx, mon in enumerate(monsters):
        pos = spawns_enemy[idx] if idx < len(spawns_enemy) else spawns_enemy[-1]
        map_state.actors.append(
            Actor(
                id=str(mon.id),
                combatant_id=mon.id,
                combatant_type="monster",
                x=pos.x,
                y=pos.y,
                name=mon.label or mon.name,
            )
        )

    # --- 初始化戰鬥 ---
    combat_state = start_combat(characters, monsters)

    return characters, monsters, map_state, combat_state
