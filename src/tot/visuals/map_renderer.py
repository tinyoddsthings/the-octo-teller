"""ASCII 地圖渲染器。

Z-index 圖層堆疊、座標軸標籤、視野裁切。
座標系為左下原點，渲染時從 y=height-1 往下印到 y=0。

Z-index 圖層（低到高）：
   0  地形（. 地板）
  10  靜態物件（# 牆壁, D 門）
  20  屍體（%）
  30  掉落物（!）
  40  活著的生物（@ 玩家, E 敵人）
"""

from __future__ import annotations

import unicodedata

from tot.models import MapState, Position


# Z-index 常數
Z_TERRAIN = 0
Z_PROP = 10
Z_CORPSE = 20
Z_ITEM = 30
Z_LIVING = 40


def _char_width(ch: str) -> int:
    """判斷字元的顯示寬度（全形=2, 半形=1）。"""
    if len(ch) != 1:
        return 1
    cat = unicodedata.east_asian_width(ch)
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

    def _build_layer_grid(self) -> list[list[tuple[str, int]]]:
        """建構含 z-index 的二維字元陣列 [y][x] = (symbol, z_index)。"""
        grid: list[list[tuple[str, int]]] = [
            [(".", Z_TERRAIN) for _ in range(self._w)]
            for _ in range(self._h)
        ]

        # 圖層 0：地形
        if self._ms.terrain:
            for y in range(self._h):
                for x in range(self._w):
                    tile = self._ms.terrain[y][x]
                    grid[y][x] = (tile.symbol, Z_TERRAIN)

        # 圖層 10：manifest 靜態 Prop
        for p in self._ms.manifest.props:
            if 0 <= p.x < self._w and 0 <= p.y < self._h:
                if not p.hidden:
                    self._place(grid, p.x, p.y, p.symbol, Z_PROP)

        # 圖層 10/30：動態 Prop（item 類型用 Z_ITEM）
        for p in self._ms.props:
            if 0 <= p.x < self._w and 0 <= p.y < self._h:
                if not p.hidden:
                    z = Z_ITEM if p.prop_type == "item" else Z_PROP
                    self._place(grid, p.x, p.y, p.symbol, z)

        # 圖層 20/40：Actor（死亡降級為屍體）
        for a in self._ms.actors:
            if 0 <= a.x < self._w and 0 <= a.y < self._h:
                if a.is_alive:
                    self._place(grid, a.x, a.y, a.symbol, Z_LIVING)
                else:
                    self._place(grid, a.x, a.y, "%", Z_CORPSE)

        return grid

    @staticmethod
    def _place(
        grid: list[list[tuple[str, int]]],
        x: int, y: int,
        symbol: str, z: int,
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
