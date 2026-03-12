"""T.O.T. Bone Engine 戰鬥狀態資料模型。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from tot.models.map import MapState, Position

CombatantRef = tuple[Literal["character", "monster"], UUID]


class MoveEvent(BaseModel):
    """移動產生的事件（供上層處理）。"""

    event_type: str  # "opportunity_attack" | "difficult_terrain"
    trigger_actor_id: str = ""  # 觸發 OA 的敵方 Actor id
    message: str = ""


class MoveResult(BaseModel):
    """move_entity 的回傳結果。"""

    success: bool
    speed_remaining: float
    events: list[MoveEvent] = Field(default_factory=list)


class AoePreview(BaseModel):
    """AoE 瞄準預覽結果。"""

    center: Position
    hit_enemies: list[str] = Field(default_factory=list)  # Actor.id 列表
    hit_allies: list[str] = Field(default_factory=list)  # 友軍誤傷 Actor.id
    all_hit_names: list[str] = Field(default_factory=list)  # 可讀名稱列表
    message: str = ""  # 預覽摘要


class TurnState(BaseModel):
    """單一回合內的動作經濟追蹤。"""

    action_used: bool = False
    bonus_action_used: bool = False
    mastery_used: bool = False  # 武器專精每回合一次
    movement_remaining: float = 0.0  # 剩餘移動距離（公尺），回合開始時由 TUI 設為 speed


class InitiativeEntry(BaseModel):
    combatant_type: Literal["character", "monster"]
    combatant_id: UUID
    initiative: int
    is_surprised: bool = False
    reaction_used: bool = False  # 反應跨回合追蹤（每輪重置）


class CombatState(BaseModel):
    """追蹤進行中的戰鬥遭遇狀態。"""

    round_number: int = 1
    current_turn_index: int = 0
    initiative_order: list[InitiativeEntry] = Field(default_factory=list)
    is_active: bool = False
    turn_state: TurnState = Field(default_factory=TurnState)
    map_state: MapState | None = None  # 有地圖時啟用空間系統

    def current_entry(self) -> InitiativeEntry | None:
        """取得當前回合的先攻條目。"""
        if not self.initiative_order:
            return None
        if self.current_turn_index >= len(self.initiative_order):
            return None
        return self.initiative_order[self.current_turn_index]
