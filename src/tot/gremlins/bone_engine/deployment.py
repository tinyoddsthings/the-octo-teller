"""佈陣階段——遭遇判定 + 戰鬥前角色放置。

狀態機：Exploration → (潛行判定) → Deployment → Combat

佈陣階段讓玩家在戰鬥開始前選擇站位。潛行判定結果決定
佈陣區大小（偷襲成功可使用擴大佈陣區）。
"""

from __future__ import annotations

import random
from uuid import UUID

from tot.gremlins.bone_engine.combat import start_combat
from tot.gremlins.bone_engine.dice import roll_d20
from tot.gremlins.bone_engine.exploration import prepare_combat_from_node
from tot.gremlins.bone_engine.spatial import place_actors_at_spawn
from tot.models import (
    Ability,
    Actor,
    Character,
    CombatState,
    DeploymentState,
    EncounterResult,
    EncounterType,
    ExplorationMap,
    MapState,
    Monster,
    Position,
    Skill,
)

# 行軍順序型別別名
MarchingOrder = list[UUID]


# ---------------------------------------------------------------------------
# 遭遇判定
# ---------------------------------------------------------------------------


def resolve_encounter(
    characters: list[Character],
    monsters: list[Monster],
    stealth_intent: bool,
    alerted: bool = False,
    rng: random.Random | None = None,
) -> EncounterResult:
    """潛行對抗察覺——決定遭遇類型。

    - alerted=True → 敵人已被驚動，直接 NORMAL（不管 stealth_intent）
    - stealth_intent=False → 直接 NORMAL
    - 每位角色擲潛行檢定 vs 敵方最高被動察覺
    - 全員通過 → SURPRISE（所有怪物被突襲）
    - 任一失敗 → NORMAL
    """
    if alerted:
        return EncounterResult(
            encounter_type=EncounterType.NORMAL,
            message="敵人已被驚動——無法發動突襲！",
        )

    if not stealth_intent:
        return EncounterResult(
            encounter_type=EncounterType.NORMAL,
            message="正常遭遇——雙方互相發現。",
        )

    # 敵方被動察覺 = 10 + WIS modifier
    enemy_perception = max(10 + mon.ability_scores.modifier(Ability.WIS) for mon in monsters)

    stealth_rolls: dict[str, int] = {}
    all_pass = True
    for char in characters:
        result = roll_d20(modifier=char.skill_bonus(Skill.STEALTH), rng=rng)
        stealth_rolls[str(char.id)] = result.total
        if result.total < enemy_perception:
            all_pass = False

    if all_pass:
        surprised_ids = {mon.id for mon in monsters}
        return EncounterResult(
            encounter_type=EncounterType.SURPRISE,
            stealth_rolls=stealth_rolls,
            enemy_perception=enemy_perception,
            surprised_ids=surprised_ids,
            message="偷襲成功！敵人毫無察覺。",
        )

    return EncounterResult(
        encounter_type=EncounterType.NORMAL,
        stealth_rolls=stealth_rolls,
        enemy_perception=enemy_perception,
        message="潛行失敗——敵人發現了你們。",
    )


# ---------------------------------------------------------------------------
# 佈陣區域
# ---------------------------------------------------------------------------


def get_spawn_zone(
    map_state: MapState,
    encounter_type: EncounterType,
) -> list[Position]:
    """依遭遇類型取得可佈陣區域。

    SURPRISE → players_surprise_zone → players_zone → players（逐層退回）
    NORMAL   → players_zone → players（退回）
    AMBUSH   → 不應呼叫（伏擊跳過佈陣）
    """
    if encounter_type == EncounterType.AMBUSH:
        msg = "伏擊場景不使用佈陣階段"
        raise ValueError(msg)

    spawns = map_state.manifest.spawn_points

    if encounter_type == EncounterType.SURPRISE:
        for key in ("players_surprise_zone", "players_zone", "players"):
            if key in spawns and spawns[key]:
                return list(spawns[key])

    # NORMAL 或 SURPRISE 沒有專用區域時
    for key in ("players_zone", "players"):
        if key in spawns and spawns[key]:
            return list(spawns[key])

    return []


# ---------------------------------------------------------------------------
# 佈陣操作
# ---------------------------------------------------------------------------


def _place_monsters(
    monsters: list[Monster],
    map_state: MapState,
) -> None:
    """將怪物放置到 enemies spawn points。"""
    enemy_spawns = map_state.manifest.spawn_points.get("enemies", [])
    for i, mon in enumerate(monsters):
        if i >= len(enemy_spawns):
            break
        sp = enemy_spawns[i]
        actor = Actor(
            id=f"mob_{i}",
            x=sp.x,
            y=sp.y,
            symbol="👹",
            combatant_id=mon.id,
            combatant_type="monster",
            name=mon.name,
            is_blocking=True,
            is_alive=mon.is_alive,
        )
        map_state.actors.append(actor)


def _place_characters(
    characters: list[Character],
    spawn_zone: list[Position],
    map_state: MapState,
    marching_order: MarchingOrder | None = None,
) -> dict[str, Position]:
    """將角色按行軍順序放置到佈陣區域。回傳放置結果。"""
    # 依行軍順序排列角色
    if marching_order:
        id_to_char = {c.id: c for c in characters}
        ordered = [id_to_char[uid] for uid in marching_order if uid in id_to_char]
        # 行軍順序裡沒有的角色排在後面
        remaining = [c for c in characters if c.id not in {uid for uid in marching_order}]
        ordered.extend(remaining)
    else:
        ordered = list(characters)

    placements: dict[str, Position] = {}
    for i, char in enumerate(ordered):
        if i >= len(spawn_zone):
            break
        sp = spawn_zone[i]
        actor = Actor(
            id=f"pc_{i}",
            x=sp.x,
            y=sp.y,
            symbol="🧙",
            combatant_id=char.id,
            combatant_type="character",
            name=char.name,
            is_blocking=True,
            is_alive=char.is_alive,
        )
        map_state.actors.append(actor)
        placements[str(char.id)] = Position(x=sp.x, y=sp.y)

    return placements


def auto_deploy(
    marching_order: MarchingOrder,
    characters: list[Character],
    monsters: list[Monster],
    map_state: MapState,
    encounter: EncounterResult,
) -> DeploymentState:
    """自動佈陣——依行軍順序放置所有戰鬥者。"""
    _place_monsters(monsters, map_state)
    spawn_zone = get_spawn_zone(map_state, encounter.encounter_type)
    placements = _place_characters(characters, spawn_zone, map_state, marching_order)

    return DeploymentState(
        map_state=map_state,
        spawn_zone=spawn_zone,
        placements=placements,
        encounter=encounter,
    )


def manual_deploy(
    deployment: DeploymentState,
    character_id: UUID,
    position: Position,
) -> DeploymentState:
    """手動調整角色位置。

    驗證：目標在佈陣區內、不與他人重疊、不在阻擋地形上。
    """
    cid = str(character_id)
    if cid not in deployment.placements:
        msg = f"角色 {cid} 不在佈陣中"
        raise ValueError(msg)

    # 檢查是否在佈陣區內
    if position not in deployment.spawn_zone:
        msg = f"位置 ({position.x}, {position.y}) 不在佈陣區域內"
        raise ValueError(msg)

    # 檢查阻擋地形
    ms = deployment.map_state
    if (
        ms.terrain
        and 0 <= position.y < len(ms.terrain)
        and 0 <= position.x < len(ms.terrain[position.y])
        and ms.terrain[position.y][position.x].is_blocking
    ):
        msg = f"位置 ({position.x}, {position.y}) 是阻擋地形"
        raise ValueError(msg)

    # 檢查靜態 Prop 阻擋
    for prop in ms.manifest.props:
        if prop.x == position.x and prop.y == position.y and prop.is_blocking:
            msg = f"位置 ({position.x}, {position.y}) 被 {prop.name} 擋住"
            raise ValueError(msg)

    # 檢查是否與其他角色重疊（不含自己）
    for other_cid, other_pos in deployment.placements.items():
        if other_cid != cid and other_pos == position:
            msg = f"位置 ({position.x}, {position.y}) 已被其他角色佔據"
            raise ValueError(msg)

    # 更新 placements
    new_placements = dict(deployment.placements)
    new_placements[cid] = position

    # 更新 Actor 位置
    actor = next(
        (a for a in ms.actors if str(a.combatant_id) == cid),
        None,
    )
    if actor:
        actor.x = position.x
        actor.y = position.y

    return deployment.model_copy(update={"placements": new_placements})


def validate_deployment(deployment: DeploymentState) -> list[str]:
    """檢查佈陣是否完備。回傳錯誤訊息列表（空 = 通過）。"""
    errors: list[str] = []

    # 檢查位置是否都在佈陣區內
    for cid, pos in deployment.placements.items():
        if pos not in deployment.spawn_zone:
            errors.append(f"角色 {cid} 的位置 ({pos.x}, {pos.y}) 不在佈陣區域內")

    # 檢查是否有重疊
    positions = list(deployment.placements.values())
    seen: set[tuple[int, int]] = set()
    for pos in positions:
        key = (pos.x, pos.y)
        if key in seen:
            errors.append(f"位置 ({pos.x}, {pos.y}) 有多個角色重疊")
        seen.add(key)

    return errors


def confirm_deployment(
    deployment: DeploymentState,
    characters: list[Character],
    monsters: list[Monster],
    rng: random.Random | None = None,
) -> CombatState:
    """確認佈陣並進入戰鬥。"""
    errors = validate_deployment(deployment)
    if errors:
        msg = "佈陣驗證失敗：" + "; ".join(errors)
        raise ValueError(msg)

    combat = start_combat(
        characters,
        monsters,
        surprised_ids=deployment.encounter.surprised_ids,
        rng=rng,
    )
    combat.map_state = deployment.map_state

    return combat


# ---------------------------------------------------------------------------
# 便捷入口
# ---------------------------------------------------------------------------


def start_deployment_from_node(
    exp_map: ExplorationMap,
    node_id: str,
    marching_order: MarchingOrder,
    characters: list[Character],
    monsters: list[Monster],
    stealth_intent: bool,
    alerted: bool = False,
    rng: random.Random | None = None,
) -> DeploymentState:
    """從探索節點啟動佈陣流程。

    prepare_combat_from_node() → resolve_encounter() → auto_deploy()
    """
    map_state = prepare_combat_from_node(exp_map, node_id)
    if map_state is None:
        msg = f"節點 {node_id} 沒有對應的戰鬥地圖"
        raise ValueError(msg)

    encounter = resolve_encounter(
        characters,
        monsters,
        stealth_intent,
        alerted=alerted,
        rng=rng,
    )

    if encounter.encounter_type == EncounterType.AMBUSH:
        # 伏擊場景——直接放置，跳過佈陣
        place_actors_at_spawn(characters, monsters, map_state)
        return DeploymentState(
            map_state=map_state,
            spawn_zone=[],
            placements={},
            encounter=encounter,
            is_confirmed=True,
        )

    return auto_deploy(marching_order, characters, monsters, map_state, encounter)
