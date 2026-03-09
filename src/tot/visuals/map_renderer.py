"""ASCII 地圖渲染器。

Z-index 圖層堆疊、座標軸標籤、視野裁切、戰爭迷霧。
座標系為左下原點，渲染時從 y=height-1 往下印到 y=0。

Z-index 圖層（低到高）：
   0  地形（空白地板）
  10  靜態物件（🧱 牆壁, 🚪 門）
  20  屍體（💀）
  30  掉落物（💎）
  40  活著的生物（🧙 玩家, 👹 敵人）

戰爭迷霧：
  render_viewport() 可指定 viewer_id，啟用後對視野內每格
  執行 Bresenham LOS 判定，被遮擋的格子替換為 ❓。
  遮擋物本身（如牆壁）仍然可見——因為角色能看見擋住自己的東西。
"""

from __future__ import annotations

import unicodedata
from uuid import UUID

from tot.models import DeploymentState, MapState, Position

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
        self._w = map_state.manifest.width
        self._h = map_state.manifest.height

    def render_full(self) -> str:
        """完整地圖（DM 視角），含座標軸標籤。"""
        grid = self._build_layer_grid()
        return self._format_grid(grid, x_offset=0, y_offset=0)

    def render_deployment(self, deployment: DeploymentState) -> str:
        """佈陣預覽地圖——用 ✦ 標示可佈陣區域。

        Z_ZONE=15 介於 Z_PROP(10) 和 Z_CORPSE(20) 之間，
        Actor 在 Z_LIVING=40 會自動覆蓋 ✦ 標記。
        """
        grid = self._build_layer_grid()
        for pos in deployment.spawn_zone:
            if 0 <= pos.x < self._w and 0 <= pos.y < self._h:
                self._place(grid, pos.x, pos.y, "✦", Z_ZONE)
        return self._format_grid(grid, x_offset=0, y_offset=0)

    def render_viewport(
        self,
        center: Position,
        radius: int,
        viewer_id: UUID | None = None,
    ) -> str:
        """局部視野渲染，可選戰爭迷霧。

        以 center 為中心、radius 為半徑裁切正方形視野。
        若提供 viewer_id，對視野內每格跑 LOS 判定，
        被遮擋的格子替換為 ❓（遮擋物本身仍可見）。
        超出地圖邊界的格子用空白填充。
        """
        full_grid = self._build_layer_grid()

        # 視野邊界（可能超出地圖）
        x_min = center.x - radius
        y_min = center.y - radius
        x_max = center.x + radius
        y_max = center.y + radius

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

        return self._format_grid(viewport, x_offset=x_min, y_offset=y_min)

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

        vp_h = len(grid)
        vp_w = len(grid[0]) if grid else 0
        fog_grid: list[list[tuple[str, int]]] = []

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
                if map_x == viewer.x and map_y == viewer.y:
                    row.append(cell)
                    continue

                target = Position(x=map_x, y=map_y)
                if has_line_of_sight(viewer, target, self._ms):
                    # 有視線 → 可見
                    row.append(cell)
                else:
                    # 沒有視線，但遮擋物本身可見（第一個擋住的格子）
                    # 判定方式：該格自身是 blocking → 仍顯示
                    if self._is_blocking_cell(map_x, map_y):
                        row.append(cell)
                    else:
                        row.append(("❓", Z_TERRAIN))

            fog_grid.append(row)

        return fog_grid

    def _is_blocking_cell(self, x: int, y: int) -> bool:
        """檢查格子本身是否為阻擋物（用於迷霧判定中保留可見的牆壁）。"""
        # 地形阻擋
        if (
            self._ms.terrain
            and 0 <= y < len(self._ms.terrain)
            and 0 <= x < len(self._ms.terrain[y])
            and self._ms.terrain[y][x].is_blocking
        ):
            return True
        # 靜態 Prop 阻擋
        for p in self._ms.manifest.props:
            if p.x == x and p.y == y and p.is_blocking:
                return True
        # 動態 Prop 阻擋
        return any(p.x == x and p.y == y and p.is_blocking for p in self._ms.props)

    def _build_layer_grid(self) -> list[list[tuple[str, int]]]:
        """建構含 z-index 的二維字元陣列 [y][x] = (symbol, z_index)。"""
        grid: list[list[tuple[str, int]]] = [
            [(".", Z_TERRAIN) for _ in range(self._w)] for _ in range(self._h)
        ]

        # 圖層 0：地形
        if self._ms.terrain:
            for y in range(self._h):
                for x in range(self._w):
                    tile = self._ms.terrain[y][x]
                    grid[y][x] = (tile.symbol, Z_TERRAIN)

        # 圖層 10：manifest 靜態 Prop
        for p in self._ms.manifest.props:
            if 0 <= p.x < self._w and 0 <= p.y < self._h and not p.hidden:
                self._place(grid, p.x, p.y, p.symbol, Z_PROP)

        # 圖層 10/30：動態 Prop（item 類型用 Z_ITEM）
        for p in self._ms.props:
            if 0 <= p.x < self._w and 0 <= p.y < self._h and not p.hidden:
                z = Z_ITEM if p.prop_type == "item" else Z_PROP
                self._place(grid, p.x, p.y, p.symbol, z)

        # 圖層 20/40：Actor（死亡降級為屍體）
        for a in self._ms.actors:
            if 0 <= a.x < self._w and 0 <= a.y < self._h:
                if a.is_alive:
                    self._place(grid, a.x, a.y, a.symbol, Z_LIVING)
                else:
                    self._place(grid, a.x, a.y, "💀", Z_CORPSE)

        return grid

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
    ) -> str:
        """將 grid 格式化為帶座標軸的字串。

        從 y=最大值 往下印到 y=最小值（左下原點）。
        """
        actual_h = len(grid)
        actual_w = len(grid[0]) if grid else 0

        # Y 軸標籤寬度
        max_y_label = y_offset + actual_h - 1
        y_label_width = max(2, len(str(max_y_label)))

        lines: list[str] = []

        # X 軸標籤（頂部）
        x_header = " " * (y_label_width + 1)
        x_labels: list[str] = []
        for x in range(actual_w):
            label = str(x + x_offset)
            # 每格佔 2 字元寬（對齊全形字）
            x_labels.append(label.rjust(2))
        x_header += " ".join(x_labels)
        lines.append(x_header)

        # 地圖本體（從上到下 = y 從大到小）
        for row_idx in range(actual_h - 1, -1, -1):
            y_label = str(row_idx + y_offset).rjust(y_label_width)
            cells: list[str] = []
            for x_idx in range(actual_w):
                symbol = grid[row_idx][x_idx][0]
                w = _char_width(symbol)
                if w == 2:
                    cells.append(symbol)
                else:
                    cells.append(f" {symbol}")
            line = f"{y_label} " + " ".join(cells)
            lines.append(line)

        return "\n".join(lines)
