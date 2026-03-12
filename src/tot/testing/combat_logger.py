"""結構化戰鬥 Log——記錄每個動作和狀態快照。

供 HeadlessCombatRunner 和規則斷言使用。
每個回合自動記錄地圖快照 + 狀態面板。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from tot.models import (
    Character,
    MapState,
    Monster,
    Position,
)
from tot.visuals.map_renderer import MapRenderer

# ---------------------------------------------------------------------------
# Log 事件資料結構
# ---------------------------------------------------------------------------


@dataclass
class LogEntry:
    """一筆 log 事件。"""

    round_num: int
    actor_id: UUID | None
    actor_name: str
    # "action" | "damage" | "death" | "move" | "round_start" | "turn_start" | "combat_end"
    event_type: str
    message: str
    # 動作細節（供斷言函式查詢）
    action_type: str = ""  # "attack" | "dodge" | "disengage" | "cast_spell" | "move" | "end_turn"
    target_id: UUID | None = None
    target_name: str = ""
    damage_dealt: int = 0
    distance_to_target: float = 0.0
    movement_used: float = 0.0
    position: Position | None = None


@dataclass
class StatusSnapshot:
    """一個時間點的角色狀態快照。"""

    combatant_id: UUID
    name: str
    hp_current: int
    hp_max: int
    ac: int
    position: tuple[float, float] | None = None  # 公尺座標
    conditions: list[str] = field(default_factory=list)
    is_alive: bool = True


@dataclass
class CombatResult:
    """戰鬥結果。"""

    winner: str  # "players" | "monsters" | "draw"
    total_rounds: int
    log: CombatLog


@dataclass
class CombatLog:
    """完整戰鬥 log。"""

    entries: list[LogEntry] = field(default_factory=list)
    # round_num → 狀態快照
    status_snapshots: dict[int, list[StatusSnapshot]] = field(
        default_factory=dict,
    )
    map_snapshots: dict[int, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CombatLogger
# ---------------------------------------------------------------------------


class CombatLogger:
    """記錄戰鬥過程為結構化資料 + ASCII 地圖快照。"""

    def __init__(self) -> None:
        self._log = CombatLog()
        self._current_round = 0

    @property
    def combat_log(self) -> CombatLog:
        return self._log

    def log_round_start(self, round_num: int) -> None:
        self._current_round = round_num
        self._log.entries.append(
            LogEntry(
                round_num=round_num,
                actor_id=None,
                actor_name="",
                event_type="round_start",
                message=f"=== 第 {round_num} 輪 ===",
            )
        )

    def log_turn_start(self, actor_id: UUID, actor_name: str) -> None:
        self._log.entries.append(
            LogEntry(
                round_num=self._current_round,
                actor_id=actor_id,
                actor_name=actor_name,
                event_type="turn_start",
                message=f"--- {actor_name} 的回合 ---",
            )
        )

    def log_action(
        self,
        actor_id: UUID,
        actor_name: str,
        action_type: str,
        message: str,
        *,
        target_id: UUID | None = None,
        target_name: str = "",
        damage_dealt: int = 0,
        distance_to_target: float = 0.0,
        movement_used: float = 0.0,
        position: Position | None = None,
    ) -> None:
        self._log.entries.append(
            LogEntry(
                round_num=self._current_round,
                actor_id=actor_id,
                actor_name=actor_name,
                event_type="action",
                message=message,
                action_type=action_type,
                target_id=target_id,
                target_name=target_name,
                damage_dealt=damage_dealt,
                distance_to_target=distance_to_target,
                movement_used=movement_used,
                position=position,
            )
        )

    def log_map_snapshot(self, map_state: MapState) -> None:
        """用 MapRenderer 產生 ASCII 地圖快照。"""
        rendered = MapRenderer(map_state).render_full()
        self._log.map_snapshots[self._current_round] = rendered

    def log_status_snapshot(
        self,
        characters: list[Character],
        monsters: list[Monster],
        map_state: MapState,
    ) -> None:
        """記錄所有戰鬥者的狀態。"""
        snapshots: list[StatusSnapshot] = []

        for char in characters:
            actor = map_state.get_actor(char.id)
            pos = (actor.x, actor.y) if actor else None
            snapshots.append(
                StatusSnapshot(
                    combatant_id=char.id,
                    name=char.name,
                    hp_current=char.hp_current,
                    hp_max=char.hp_max,
                    ac=char.ac,
                    position=pos,
                    conditions=[c.condition.value for c in char.conditions],
                    is_alive=char.is_alive,
                )
            )

        for mon in monsters:
            actor = map_state.get_actor(mon.id)
            pos = (actor.x, actor.y) if actor else None
            snapshots.append(
                StatusSnapshot(
                    combatant_id=mon.id,
                    name=mon.label or mon.name,
                    hp_current=mon.hp_current,
                    hp_max=mon.hp_max,
                    ac=mon.ac,
                    position=pos,
                    conditions=[c.condition.value for c in mon.conditions],
                    is_alive=mon.is_alive,
                )
            )

        self._log.status_snapshots[self._current_round] = snapshots

    def log_combat_end(self, result: str, total_rounds: int) -> None:
        self._log.entries.append(
            LogEntry(
                round_num=self._current_round,
                actor_id=None,
                actor_name="",
                event_type="combat_end",
                message=f"戰鬥結束：{result}（共 {total_rounds} 輪）",
            )
        )

    def save(self, path: Path) -> None:
        """寫入人類可讀的 log 檔案。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = ["=== T.O.T. 自動對戰紀錄 ===\n"]

        for entry in self._log.entries:
            if entry.event_type == "round_start":
                lines.append(f"\n{entry.message}")
                # 附加地圖快照
                map_snap = self._log.map_snapshots.get(entry.round_num)
                if map_snap:
                    lines.append("\n【地圖快照】")
                    lines.append(map_snap)
                # 附加狀態快照
                status_snaps = self._log.status_snapshots.get(entry.round_num)
                if status_snaps:
                    lines.append("\n【狀態面板】")
                    for s in status_snaps:
                        pos_str = (
                            f"  位置: ({s.position[0]:.1f},{s.position[1]:.1f})"
                            if s.position
                            else ""
                        )
                        cond_str = f"  [{', '.join(s.conditions)}]" if s.conditions else ""
                        alive_str = "  [倒下]" if not s.is_alive else ""
                        lines.append(
                            f"  {s.name:<10s} HP: {s.hp_current:>2d}/{s.hp_max:>2d}  "
                            f"AC: {s.ac}{pos_str}{cond_str}{alive_str}"
                        )
            elif entry.event_type == "turn_start":
                lines.append(f"\n{entry.message}")
            else:
                lines.append(f"  {entry.message}")

        path.write_text("\n".join(lines), encoding="utf-8")
