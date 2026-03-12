"""ASCII 地圖渲染器。

Z-index 圖層堆疊、座標軸標籤、視野裁切、戰爭迷霧。
座標系為左下原點，渲染時從 y=height-1 往下印到 y=0。

內部保留 display grid（每格 1.5m = 5ft），用於 ASCII 字元顯示，
但不依賴 terrain[y][x] 陣列——牆壁從 Wall AABB 推算。

Z-index 圖層（低到高）：
   0  地形（空白地板）
  10  靜態物件（🧱 牆壁, 🚪 門）
  20  屍體（💀）
  30  掉落物（💎）
  40  活著的生物（🧙 玩家, 👹 敵人）

戰爭迷霧：
  render_viewport() 可指定 viewer_id，啟用後對視野內每格
  執行 Ray-AABB LOS 判定，被遮擋的格子替換為 ❓。
  遮擋物本身（如牆壁）仍然可見——因為角色能看見擋住自己的東西。
"""

from __future__ import annotations

import math
import unicodedata
from uuid import UUID

from tot.models import DeploymentState, MapState, Position

# 顯示用格大小（公尺）——1 display cell = 1.5m = 5ft
_DISPLAY_CELL = 1.5

# Z-index 常數
Z_TERRAIN = 0
Z_PROP = 10
Z_ZONE = 15
Z_CORPSE = 20
Z_ITEM = 30
Z_LIVING = 40


def _char_width(ch: str) -> int:
    """判斷字元的顯示寬度（全形/emoji=2, 半形=1）。"""
    if not ch:
        return 1
    cp = ord(ch[0])
    # emoji 範圍（常見區段）一律視為寬度 2
    if cp >= 0x1F000:
        return 2
    cat = unicodedata.east_asian_width(ch[0])
    return 2 if cat in ("W", "F") else 1


class MapRenderer:
    """ASCII 地圖渲染器。"""

    def __init__(self, map_state: MapState) -> None:
        self._ms = map_state
        # display grid 尺寸（每格 1.5m）
        self._w = max(1, int(map_state.manifest.width / _DISPLAY_CELL))
        self._h = max(1, int(map_state.manifest.height / _DISPLAY_CELL))

    def render_full(self, *, rich_markup: bool = False) -> str:
        """完整地圖（DM 視角），含座標軸標籤。

        rich_markup=True 時，重疊格用 Rich 背景色標記。
        """
        grid = self._build_layer_grid()
        overlaps = self._build_overlap_map() if rich_markup else None
        return self._format_grid(grid, x_offset=0, y_offset=0, overlaps=overlaps)

    def render_deployment(self, deployment: DeploymentState) -> str:
        """佈陣預覽地圖——用 ✦ 標示可佈陣區域。

        Z_ZONE=15 介於 Z_PROP(10) 和 Z_CORPSE(20) 之間，
        Actor 在 Z_LIVING=40 會自動覆蓋 ✦ 標記。
        """
        grid = self._build_layer_grid()
        for pos in deployment.spawn_zone:
            gx, gy = self._m_to_cell(pos.x, pos.y)
            if 0 <= gx < self._w and 0 <= gy < self._h:
                self._place(grid, gx, gy, "✦", Z_ZONE)
        overlaps = self._build_overlap_map()
        return self._format_grid(grid, x_offset=0, y_offset=0, overlaps=overlaps)

    def render_viewport(
        self,
        center: Position,
        radius: int,
        viewer_id: UUID | None = None,
    ) -> str:
        """局部視野渲染，可選戰爭迷霧。

        以 center 為中心、radius 為半徑裁切正方形視野（display cell 單位）。
        center 為公尺座標，內部轉為 display cell 座標。
        若提供 viewer_id，對視野內每格跑 LOS 判定，
        被遮擋的格子替換為 ❓（遮擋物本身仍可見）。
        超出地圖邊界的格子用空白填充。
        """
        full_grid = self._build_layer_grid()
        cgx, cgy = self._m_to_cell(center.x, center.y)

        # 視野邊界（可能超出地圖）——用網格座標
        x_min = cgx - radius
        y_min = cgy - radius
        x_max = cgx + radius
        y_max = cgy + radius

        # 裁切子格：超出邊界填空白
        viewport: list[list[tuple[str, int]]] = []
        for vy in range(y_min, y_max + 1):
            row: list[tuple[str, int]] = []
            for vx in range(x_min, x_max + 1):
                if 0 <= vx < self._w and 0 <= vy < self._h:
                    row.append(full_grid[vy][vx])
                else:
                    row.append((" ", Z_TERRAIN))
            viewport.append(row)

        # 戰爭迷霧
        if viewer_id is not None:
            viewport = self._apply_fog_of_war(
                viewport,
                center,
                radius,
                x_min,
                y_min,
            )

        overlaps = self._build_overlap_map()
        return self._format_grid(viewport, x_offset=x_min, y_offset=y_min, overlaps=overlaps)

    def _apply_fog_of_war(
        self,
        grid: list[list[tuple[str, int]]],
        viewer: Position,
        radius: int,
        x_offset: int,
        y_offset: int,
    ) -> list[list[tuple[str, int]]]:
        """對每格跑 has_line_of_sight()，被遮擋的格子替換為 ❓。

        規則：
        - 觀察者自己的格子永遠可見
        - 有 LOS 的格子可見
        - 沒有 LOS 但自身是 is_blocking 的格子仍可見（能看見擋住自己的牆）
        - 超出地圖邊界的格子保持空白（不顯示 ❓）
        """
        from tot.gremlins.bone_engine.spatial import has_line_of_sight

        dc = _DISPLAY_CELL
        vp_h = len(grid)
        vp_w = len(grid[0]) if grid else 0
        fog_grid: list[list[tuple[str, int]]] = []

        vgx, vgy = self._m_to_cell(viewer.x, viewer.y)

        for vy in range(vp_h):
            row: list[tuple[str, int]] = []
            map_y = vy + y_offset
            for vx in range(vp_w):
                map_x = vx + x_offset
                cell = grid[vy][vx]

                # 超出地圖邊界 → 維持空白
                if not (0 <= map_x < self._w and 0 <= map_y < self._h):
                    row.append(cell)
                    continue

                # 觀察者自己的格子 → 永遠可見
                if map_x == vgx and map_y == vgy:
                    row.append(cell)
                    continue

                # 轉為公尺座標（display cell 中心）做視線判定
                target = Position(x=map_x * dc + dc / 2, y=map_y * dc + dc / 2)
                if has_line_of_sight(viewer, target, self._ms):
                    row.append(cell)
                else:
                    if self._is_blocking_cell(map_x, map_y):
                        row.append(cell)
                    else:
                        row.append(("❓", Z_TERRAIN))

            fog_grid.append(row)

        return fog_grid

    def _is_blocking_cell(self, x: int, y: int) -> bool:
        """檢查 display cell 是否為阻擋物（用於迷霧判定中保留可見的牆壁）。"""
        dc = _DISPLAY_CELL
        # cell AABB（公尺）
        cx0 = x * dc
        cy0 = y * dc
        cx1 = cx0 + dc
        cy1 = cy0 + dc
        # 牆壁阻擋
        for wall in [*self._ms.manifest.walls, *self._ms.walls]:
            wx1 = wall.x + wall.width
            wy1 = wall.y + wall.height
            if wall.x < cx1 and wx1 > cx0 and wall.y < cy1 and wy1 > cy0:
                return True
        # Prop 阻擋
        for p in [*self._ms.manifest.props, *self._ms.props]:
            if p.is_blocking and cx0 <= p.x < cx1 and cy0 <= p.y < cy1:
                return True
        return False

    def describe_cell(self, gx: int, gy: int) -> list[str]:
        """列出指定 display cell 上的所有實體描述（look 指令用）。

        回傳可讀字串列表，例如 ['🧙 Hero (玩家)', '👹 Goblin (敵人)']。
        """
        dc = _DISPLAY_CELL
        cx0 = gx * dc
        cy0 = gy * dc
        cx1 = cx0 + dc
        cy1 = cy0 + dc
        descriptions: list[str] = []

        # 牆壁
        for wall in [*self._ms.manifest.walls, *self._ms.walls]:
            wx1 = wall.x + wall.width
            wy1 = wall.y + wall.height
            if wall.x < cx1 and wx1 > cx0 and wall.y < cy1 and wy1 > cy0:
                descriptions.append(f"{wall.symbol} {wall.name}")
                break

        # Prop（manifest + 動態）
        for p in [*self._ms.manifest.props, *self._ms.props]:
            if cx0 <= p.x < cx1 and cy0 <= p.y < cy1 and not p.hidden:
                descriptions.append(f"{p.symbol} {p.name or p.prop_type}")

        # Actor
        for a in self._ms.actors:
            if cx0 <= a.x < cx1 and cy0 <= a.y < cy1:
                status = "💀" if not a.is_alive else ""
                ctype = "玩家" if a.combatant_type == "character" else "敵人"
                descriptions.append(f"{a.symbol} {a.name} ({ctype}){status}")

        return descriptions

    @staticmethod
    def _m_to_cell(x: float, y: float) -> tuple[int, int]:
        """公尺座標 → display cell 座標（每格 1.5m）。"""
        return int(math.floor(x / _DISPLAY_CELL)), int(math.floor(y / _DISPLAY_CELL))

    def _build_layer_grid(self) -> list[list[tuple[str, int]]]:
        """建構含 z-index 的二維字元陣列 [y][x] = (symbol, z_index)。"""
        grid: list[list[tuple[str, int]]] = [
            [(".", Z_TERRAIN) for _ in range(self._w)] for _ in range(self._h)
        ]
        dc = _DISPLAY_CELL

        # 圖層 0+10：牆壁（Wall AABB → 覆蓋所有相交的 display cell）
        for wall in [*self._ms.manifest.walls, *self._ms.walls]:
            gx0 = max(0, int(math.floor(wall.x / dc)))
            gy0 = max(0, int(math.floor(wall.y / dc)))
            gx1 = min(self._w, int(math.ceil((wall.x + wall.width) / dc)))
            gy1 = min(self._h, int(math.ceil((wall.y + wall.height) / dc)))
            for gy in range(gy0, gy1):
                for gx in range(gx0, gx1):
                    self._place(grid, gx, gy, wall.symbol, Z_PROP)

        # 圖層 10：manifest 靜態 Prop
        for p in self._ms.manifest.props:
            gx, gy = self._m_to_cell(p.x, p.y)
            if 0 <= gx < self._w and 0 <= gy < self._h and not p.hidden:
                self._place(grid, gx, gy, p.symbol, Z_PROP)

        # 圖層 10/30：動態 Prop
        for p in self._ms.props:
            gx, gy = self._m_to_cell(p.x, p.y)
            if 0 <= gx < self._w and 0 <= gy < self._h and not p.hidden:
                z = Z_ITEM if p.prop_type == "item" else Z_PROP
                self._place(grid, gx, gy, p.symbol, z)

        # 圖層 20/40：Actor
        for a in self._ms.actors:
            gx, gy = self._m_to_cell(a.x, a.y)
            if 0 <= gx < self._w and 0 <= gy < self._h:
                if a.is_alive:
                    self._place(grid, gx, gy, a.symbol, Z_LIVING)
                else:
                    self._place(grid, gx, gy, "💀", Z_CORPSE)

        return grid

    def _build_overlap_map(self) -> set[tuple[int, int]]:
        """找出有 2+ 個實體（Actor 或非地形 Prop）重疊的 display cell。"""
        counts: dict[tuple[int, int], int] = {}

        for p in [*self._ms.manifest.props, *self._ms.props]:
            if p.hidden:
                continue
            key = self._m_to_cell(p.x, p.y)
            if 0 <= key[0] < self._w and 0 <= key[1] < self._h:
                counts[key] = counts.get(key, 0) + 1

        for a in self._ms.actors:
            key = self._m_to_cell(a.x, a.y)
            if 0 <= key[0] < self._w and 0 <= key[1] < self._h:
                counts[key] = counts.get(key, 0) + 1

        return {k for k, v in counts.items() if v >= 2}

    @staticmethod
    def _place(
        grid: list[list[tuple[str, int]]],
        x: int,
        y: int,
        symbol: str,
        z: int,
    ) -> None:
        """只在 z-index 更高時覆蓋。"""
        if z >= grid[y][x][1]:
            grid[y][x] = (symbol, z)

    def _format_grid(
        self,
        grid: list[list[tuple[str, int]]],
        x_offset: int,
        y_offset: int,
        overlaps: set[tuple[int, int]] | None = None,
    ) -> str:
        """將 grid 格式化為帶座標軸的字串。

        Y 軸標籤在左側，X 軸標籤在底部。
        從 y=最大值 往下印到 y=最小值（左下原點）。
        overlaps 不為 None 時，重疊格用 Rich 背景色 [on dark_red] 標記。
        """
        actual_h = len(grid)
        actual_w = len(grid[0]) if grid else 0

        # Y 軸標籤寬度
        max_y_label = y_offset + actual_h - 1
        y_label_width = max(2, len(str(max_y_label)))

        lines: list[str] = []

        # 地圖本體（從上到下 = y 從大到小）
        for row_idx in range(actual_h - 1, -1, -1):
            y_label = str(row_idx + y_offset).rjust(y_label_width)
            cells: list[str] = []
            for x_idx in range(actual_w):
                symbol = grid[row_idx][x_idx][0]
                w = _char_width(symbol)
                cell_str = symbol if w == 2 else f" {symbol}"

                # 重疊標記（Rich markup）
                if overlaps and (x_idx + x_offset, row_idx + y_offset) in overlaps:
                    cell_str = f"[on dark_red]{cell_str}[/]"

                cells.append(cell_str)
            line = f"{y_label} " + " ".join(cells)
            lines.append(line)

        # X 軸標籤（底部）
        x_header = " " * (y_label_width + 1)
        x_labels: list[str] = []
        for x in range(actual_w):
            label = str(x + x_offset)
            x_labels.append(label.rjust(2))
        x_header += " ".join(x_labels)
        lines.append(x_header)

        return "\n".join(lines)
