"""AoE 瞄準系統——區域法術的目標選擇、預覽、友軍警告。

Smart Targeting 流程：
1. 玩家施放 AoE 法術
2. 系統列出射程內可選目標
3. 玩家選擇 1+ 個目標作為中心參考
4. 單選 → 以該目標位置為 AoE 中心
5. 多選 → 取質心 (centroid)
6. 預覽命中單位，⚠️ 標記友軍
7. 確認或重選

形狀判定：
- sphere：圓形，distance(center, target) ≤ radius
- cube：以施法者前方為起點的正方形，邊長 = aoe_width_ft
- cone：dot-product 角度判定，半角 cos ≈ 2/√5 ≈ 0.894
- line：沿方向的矩形，寬 5ft / 長由法術決定
"""

from __future__ import annotations

import math

from tot.gremlins.bone_engine.spatial import distance
from tot.models import Actor, AoePreview, AoeShape, MapState, Position, Spell

# D&D 5e 錐形半角餘弦值
# 錐形起點寬度 0，終點寬度 = 長度 → 半角 = atan(1/2) ≈ 26.57°
# cos(26.57°) = 2/√5 ≈ 0.894427
CONE_HALF_ANGLE_COS = 2.0 / math.sqrt(5.0)

# 呎 → 公尺
_FT_TO_M = 1.5 / 5.0  # 5ft = 1.5m


def ft_to_m(ft: float) -> float:
    """呎轉公尺。"""
    return ft * _FT_TO_M


# ---------------------------------------------------------------------------
# 質心計算
# ---------------------------------------------------------------------------


def compute_aoe_center(actors: list[Actor]) -> Position:
    """取選中目標的質心作為 AoE 中心。"""
    if not actors:
        msg = "至少需要一個目標"
        raise ValueError(msg)
    if len(actors) == 1:
        return Position(x=actors[0].x, y=actors[0].y)
    cx = sum(a.x for a in actors) / len(actors)
    cy = sum(a.y for a in actors) / len(actors)
    return Position(x=cx, y=cy)


# ---------------------------------------------------------------------------
# 形狀命中判定
# ---------------------------------------------------------------------------


def _in_sphere(target: Position, center: Position, radius_m: float) -> bool:
    """圓形範圍判定。"""
    return distance(center, target) <= radius_m


def _in_cube(
    target: Position,
    origin: Position,
    direction: Position,
    side_m: float,
) -> bool:
    """立方體範圍判定。

    D&D 5e cube：origin 是施法者位置（cube 的一面靠在施法者身上），
    向 direction 方向延伸 side_m。
    簡化為：target 在 origin→direction 方向的距離 ≤ side_m，
    且橫向偏移 ≤ side_m/2。
    """
    dx = direction.x - origin.x
    dy = direction.y - origin.y
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-9:
        # 方向不明 → 以 origin 為中心的正方形
        return abs(target.x - origin.x) <= side_m / 2 and abs(target.y - origin.y) <= side_m / 2
    # 單位向量
    ux, uy = dx / length, dy / length
    # 目標相對 origin 的向量
    rx = target.x - origin.x
    ry = target.y - origin.y
    # 投影到方向軸（前方距離）
    forward = rx * ux + ry * uy
    # 投影到橫向軸
    lateral = abs(rx * (-uy) + ry * ux)
    return 0 <= forward <= side_m and lateral <= side_m / 2


def _in_cone(
    target: Position,
    origin: Position,
    direction: Position,
    length_m: float,
) -> bool:
    """錐形範圍判定（dot-product 法）。

    origin = 施法者位置（錐形頂點）
    direction = 瞄準方向的參考點（AoE center）
    length_m = 錐形長度（公尺）
    """
    # 方向向量
    dir_x = direction.x - origin.x
    dir_y = direction.y - origin.y
    dir_len = math.sqrt(dir_x * dir_x + dir_y * dir_y)
    if dir_len < 1e-9:
        return False  # 方向不明

    # 目標相對 origin 的向量
    to_x = target.x - origin.x
    to_y = target.y - origin.y
    to_len = math.sqrt(to_x * to_x + to_y * to_y)
    if to_len < 1e-9:
        return True  # 在原點上

    # 距離檢查
    if to_len > length_m:
        return False

    # dot-product 角度檢查
    cos_angle = (dir_x * to_x + dir_y * to_y) / (dir_len * to_len)
    return cos_angle >= CONE_HALF_ANGLE_COS


def _in_line(
    target: Position,
    origin: Position,
    direction: Position,
    length_m: float,
    width_m: float,
) -> bool:
    """線形範圍判定（矩形）。"""
    dx = direction.x - origin.x
    dy = direction.y - origin.y
    d_len = math.sqrt(dx * dx + dy * dy)
    if d_len < 1e-9:
        return False
    ux, uy = dx / d_len, dy / d_len
    rx = target.x - origin.x
    ry = target.y - origin.y
    forward = rx * ux + ry * uy
    lateral = abs(rx * (-uy) + ry * ux)
    return 0 <= forward <= length_m and lateral <= width_m / 2


# ---------------------------------------------------------------------------
# 命中單位查詢
# ---------------------------------------------------------------------------


def get_actors_in_aoe(
    center: Position,
    spell: Spell,
    caster_pos: Position,
    map_state: MapState,
    *,
    alive_only: bool = True,
) -> list[Actor]:
    """取得 AoE 範圍內的所有 Actor。"""
    if spell.aoe.shape is None:
        return []

    shape = spell.aoe.shape
    actors = map_state.actors
    if alive_only:
        actors = [a for a in actors if a.is_alive]

    hit: list[Actor] = []

    if shape == AoeShape.SPHERE:
        radius_m = ft_to_m(spell.aoe.radius_ft)
        for a in actors:
            pos = Position(x=a.x, y=a.y)
            if _in_sphere(pos, center, radius_m):
                hit.append(a)

    elif shape == AoeShape.CONE:
        length_m = ft_to_m(spell.aoe.length_ft)
        for a in actors:
            pos = Position(x=a.x, y=a.y)
            if _in_cone(pos, caster_pos, center, length_m):
                hit.append(a)

    elif shape == AoeShape.CUBE:
        side_m = ft_to_m(spell.aoe.width_ft)
        for a in actors:
            pos = Position(x=a.x, y=a.y)
            if _in_cube(pos, caster_pos, center, side_m):
                hit.append(a)

    elif shape == AoeShape.LINE:
        length_m = ft_to_m(spell.aoe.length_ft)
        width_m = ft_to_m(spell.aoe.width_ft) if spell.aoe.width_ft else ft_to_m(5)
        for a in actors:
            pos = Position(x=a.x, y=a.y)
            if _in_line(pos, caster_pos, center, length_m, width_m):
                hit.append(a)

    return hit


# ---------------------------------------------------------------------------
# 友軍誤傷檢查
# ---------------------------------------------------------------------------


def check_friendly_fire(
    hit_actors: list[Actor],
    caster_allies: set[str],
) -> list[Actor]:
    """從命中列表中篩出友軍。caster_allies 是友方 combatant_id 字串集。"""
    return [a for a in hit_actors if str(a.combatant_id) in caster_allies]


# ---------------------------------------------------------------------------
# 預覽
# ---------------------------------------------------------------------------


def preview_aoe(
    center: Position,
    spell: Spell,
    caster_pos: Position,
    map_state: MapState,
    caster_allies: set[str],
) -> AoePreview:
    """產生 AoE 預覽——列出命中的敵友、組合摘要訊息。"""
    hit = get_actors_in_aoe(center, spell, caster_pos, map_state)
    friendly = check_friendly_fire(hit, caster_allies)
    friendly_ids = {a.id for a in friendly}
    enemies = [a for a in hit if a.id not in friendly_ids]

    names: list[str] = []
    for a in hit:
        tag = " ⚠️友軍" if a.id in friendly_ids else ""
        names.append(f"{a.name}{tag}")

    msg_parts: list[str] = [f"🎯 {spell.name} 預覽"]
    msg_parts.append(f"中心：({center.x:.1f}, {center.y:.1f})")
    if enemies:
        msg_parts.append(f"命中敵人 {len(enemies)} 名")
    if friendly:
        msg_parts.append(f"⚠️ 友軍誤傷 {len(friendly)} 名！")
    if not hit:
        msg_parts.append("無命中目標")

    return AoePreview(
        center=center,
        hit_enemies=[a.id for a in enemies],
        hit_allies=[a.id for a in friendly],
        all_hit_names=names,
        message="｜".join(msg_parts),
    )
