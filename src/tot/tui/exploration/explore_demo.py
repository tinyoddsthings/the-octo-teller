"""探索 Demo 場景初始化——沿用戰鬥 demo 的 3 PC，載入 tutorial_dungeon。

提供 create_exploration_demo() 建立探索場景。
支援 load_map() 切換地圖（dungeon / town / wilderness）。
"""

from __future__ import annotations

from tot.data.loader import load_exploration_map
from tot.models import (
    Ability,
    AbilityScores,
    Character,
    ExplorationMap,
    ExplorationState,
    Skill,
    SpellSlots,
    Weapon,
)
from tot.models.enums import DamageType, WeaponProperty

# 可用地圖名稱 → JSON 檔名對照
AVAILABLE_MAPS: dict[str, str] = {
    "dungeon": "tutorial_dungeon",
    "ruins": "cliff_ruins",
    "town": "starter_town",
    "wilderness": "wilderness_trail",
}


def create_demo_characters() -> list[Character]:
    """建立 3 PC 探索隊伍（同戰鬥 demo）。"""
    fighter = Character(
        name="Aldric",
        class_levels={"Fighter": 5},
        ability_scores=AbilityScores(STR=16, DEX=12, CON=14, INT=10, WIS=12, CHA=8),
        proficiency_bonus=3,
        hp_max=44,
        hp_current=44,
        hit_dice_remaining={10: 5},
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
        class_levels={"Cleric": 5},
        ability_scores=AbilityScores(STR=14, DEX=10, CON=14, INT=10, WIS=18, CHA=12),
        proficiency_bonus=3,
        hp_max=38,
        hp_current=38,
        hit_dice_remaining={8: 5},
        ac=18,
        speed=9,
        skill_proficiencies=[Skill.MEDICINE, Skill.RELIGION],
        saving_throw_proficiencies=[Ability.WIS, Ability.CHA],
        weapons=[
            Weapon(
                name="戰錘",
                damage_dice="1d8",
                damage_type=DamageType.BLUDGEONING,
            ),
        ],
        spell_dc=15,
        spell_attack=7,
        spell_slots=SpellSlots(
            max_slots={1: 4, 2: 3, 3: 2},
            current_slots={1: 4, 2: 3, 3: 2},
        ),
        spells_prepared=["神聖火焰", "療傷術", "祝福術"],
        is_ai_controlled=True,
    )

    wizard = Character(
        name="陶德",
        class_levels={"Wizard": 5},
        ability_scores=AbilityScores(STR=8, DEX=14, CON=12, INT=18, WIS=12, CHA=10),
        proficiency_bonus=3,
        hp_max=27,
        hp_current=27,
        hit_dice_remaining={6: 5},
        ac=15,
        speed=9,
        skill_proficiencies=[Skill.ARCANA, Skill.INVESTIGATION],
        saving_throw_proficiencies=[Ability.INT, Ability.WIS],
        weapons=[
            Weapon(
                name="匕首",
                damage_dice="1d4",
                damage_type=DamageType.PIERCING,
                properties=[
                    WeaponProperty.FINESSE,
                    WeaponProperty.LIGHT,
                    WeaponProperty.THROWN,
                ],
                range_normal=1,
                range_long=18,
            ),
        ],
        spell_dc=15,
        spell_attack=7,
        spell_slots=SpellSlots(
            max_slots={1: 4, 2: 3, 3: 2},
            current_slots={1: 4, 2: 3, 3: 2},
        ),
        spells_prepared=["火焰箭", "魔法飛彈", "護盾術", "火球術"],
        spells_known=["火焰箭", "魔法飛彈", "護盾術", "火球術", "法師護甲"],
        is_ai_controlled=False,
    )

    return [fighter, cleric, wizard]


def load_map(map_key: str = "dungeon") -> ExplorationMap:
    """載入探索地圖。map_key: dungeon / town / wilderness。"""
    name = AVAILABLE_MAPS.get(map_key)
    if name is None:
        msg = f"未知地圖：{map_key}（可用：{', '.join(AVAILABLE_MAPS)}）"
        raise ValueError(msg)
    return load_exploration_map(name=name)


def create_exploration_demo(
    map_key: str = "ruins",
) -> tuple[list[Character], ExplorationMap, ExplorationState]:
    """建立完整探索場景。

    回傳 (characters, exp_map, state)。
    """
    characters = create_demo_characters()
    exp_map = load_map(map_key)

    state = ExplorationState(
        current_map_id=exp_map.id,
        current_node_id=exp_map.entry_node_id,
        discovered_nodes={exp_map.entry_node_id},
    )

    # 標記入口為已造訪
    for node in exp_map.nodes:
        if node.id == exp_map.entry_node_id:
            node.is_visited = True
            break

    return characters, exp_map, state
