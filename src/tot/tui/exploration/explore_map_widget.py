"""Pointcrawl 節點圖 Widget——ASCII 拓樸圖渲染。

按海拔分層顯示：同層節點水平排列，跨層連接以箭頭標注。

符號規則：
  ● 當前位置（綠）
  ○ 已造訪（青）
  ◌ 已發現未造訪（灰）
  ── 普通路徑
  ↕↕ 跳躍路徑（黃）
  ─🔒─ 上鎖（紅）
  ┄┄ 隱藏通道（已發現，洋紅）
  ⤵ 單向路徑
  ↑/↓ 跨海拔連接
"""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

from tot.models import ExplorationEdge, ExplorationMap, ExplorationNode, ExplorationState


class ExploreMapWidget(Static):
    """Pointcrawl 節點地圖面板。"""

    map_state: reactive[ExplorationMap | None] = reactive(None)
    explore_state: reactive[ExplorationState | None] = reactive(None)

    def render(self) -> str:
        if not self.map_state or not self.explore_state:
            return "[dim]等待地圖載入...[/]"
        return self._render_map(self.map_state, self.explore_state)

    # ------------------------------------------------------------------
    # 主渲染
    # ------------------------------------------------------------------

    def _render_map(self, exp_map: ExplorationMap, state: ExplorationState) -> str:
        """渲染 ASCII 拓樸圖：節點按海拔分層，同層水平連線。"""
        lines: list[str] = []
        lines.append(f"[bold white]📍 {exp_map.name}[/]")
        lines.append("")

        visible_nodes = [
            n
            for n in exp_map.nodes
            if n.id in state.discovered_nodes or n.is_visited or n.is_discovered
        ]
        visible_edges = self._get_visible_edges(exp_map, state)
        visible_node_ids = {n.id for n in visible_nodes}

        if not visible_nodes:
            lines.append("[dim]尚未探索任何區域[/]")
            return "\n".join(lines)

        # BFS column 排列順序
        columns = self._compute_columns(exp_map, visible_nodes, visible_edges)

        # 按海拔分組（高→低）
        elevations = sorted({n.elevation_m for n in visible_nodes}, reverse=True)
        use_groups = len(elevations) > 1

        for elev in elevations:
            group = sorted(
                [n for n in visible_nodes if n.elevation_m == elev],
                key=lambda n: columns.get(n.id, 999),
            )

            # 海拔標題
            if use_groups:
                sign = "+" if elev > 0 else ""
                lines.append(f"[dim]── {sign}{int(elev)}m ──[/]")

            # 水平節點列（節點 + 同層連接符）
            row_parts: list[str] = []
            for i, node in enumerate(group):
                if i > 0:
                    connector = self._same_level_connector(group[i - 1], node, visible_edges)
                    row_parts.append(connector)
                row_parts.append(self._node_str(node, state))
            lines.append("  " + "".join(row_parts))

            # 跨海拔路徑標注（從本層出發的邊）
            for note in self._cross_level_notes(
                elev, group, visible_edges, exp_map, visible_node_ids
            ):
                lines.append(f"  {note}")
            lines.append("")  # 行距補償（iTerm2 零行距模式）

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # BFS column 排列
    # ------------------------------------------------------------------

    def _compute_columns(
        self,
        exp_map: ExplorationMap,
        visible_nodes: list[ExplorationNode],
        visible_edges: list[ExplorationEdge],
    ) -> dict[str, int]:
        """BFS 從入口出發，為每個可見節點分配水平排列序號。"""
        visible_ids = {n.id for n in visible_nodes}
        order: dict[str, int] = {}

        start_id = exp_map.entry_node_id
        if start_id not in visible_ids and visible_nodes:
            start_id = visible_nodes[0].id

        queue = [start_id]
        order[start_id] = 0

        while queue:
            current = queue.pop(0)
            for edge in visible_edges:
                neighbors: list[str] = []
                if edge.from_node_id == current:
                    neighbors.append(edge.to_node_id)
                if edge.to_node_id == current and not edge.is_one_way:
                    neighbors.append(edge.from_node_id)
                for neighbor in neighbors:
                    if neighbor in visible_ids and neighbor not in order:
                        order[neighbor] = len(order)
                        queue.append(neighbor)

        # 未被 BFS 到的節點（孤立）
        for node in visible_nodes:
            if node.id not in order:
                order[node.id] = len(order)

        return order

    # ------------------------------------------------------------------
    # 連接符 / 節點字串
    # ------------------------------------------------------------------

    def _same_level_connector(
        self,
        node_a: ExplorationNode,
        node_b: ExplorationNode,
        visible_edges: list[ExplorationEdge],
    ) -> str:
        """找相鄰同海拔節點間的連接符。"""
        for edge in visible_edges:
            a_to_b = edge.from_node_id == node_a.id and edge.to_node_id == node_b.id
            b_to_a = (
                edge.from_node_id == node_b.id
                and edge.to_node_id == node_a.id
                and not edge.is_one_way
            )
            if not (a_to_b or b_to_a):
                continue
            if edge.requires_jump:
                return "[yellow]↕↕[/]"
            if edge.is_locked:
                return "[red]─🔒─[/]"
            if edge.hidden_dc > 0:
                return "[magenta]┄┄[/]"
            return "──"
        return "  "  # 無直接邊，空格分隔

    def _node_str(self, node: ExplorationNode, state: ExplorationState) -> str:
        """節點 Rich markup 字串。"""
        npc = "[yellow]![/]" if node.npcs else ""
        if node.id == state.current_node_id:
            return f"[bold green]●{node.name}[/]{npc}"
        if node.is_visited:
            return f"[cyan]○{node.name}[/]{npc}"
        return f"[dim]◌{node.name}[/]{npc}"

    # ------------------------------------------------------------------
    # 跨海拔標注
    # ------------------------------------------------------------------

    def _cross_level_notes(
        self,
        elev: float,
        group: list[ExplorationNode],
        visible_edges: list[ExplorationEdge],
        exp_map: ExplorationMap,
        visible_node_ids: set[str],
    ) -> list[str]:
        """列出從本層節點出發的跨海拔路徑標注。"""
        group_ids = {n.id for n in group}
        notes: list[str] = []
        seen: set[str] = set()

        for edge in visible_edges:
            if edge.id in seen:
                continue
            from_in = edge.from_node_id in group_ids
            to_in = edge.to_node_id in group_ids

            # 必須恰好一端在本層
            if from_in == to_in:
                continue

            from_node = next((n for n in exp_map.nodes if n.id == edge.from_node_id), None)
            to_node = next((n for n in exp_map.nodes if n.id == edge.to_node_id), None)
            if not from_node or not to_node:
                continue
            if from_node.elevation_m == to_node.elevation_m:
                continue

            # 只列從本層出發的邊
            if not from_in:
                continue
            if to_node.id not in visible_node_ids:
                continue

            seen.add(edge.id)
            direction = "↓" if to_node.elevation_m < elev else "↑"
            edge_label = edge.name or edge.id

            if edge.requires_jump:
                arrow = f"[yellow]{direction}↕[/]"
            elif edge.is_one_way:
                arrow = f"[dim]{direction}⤵[/]"
            else:
                arrow = f"[dim]{direction}[/]"

            notes.append(f"{arrow}[dim] {edge_label} → {to_node.name}[/]")

        return notes

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _get_visible_edges(
        self,
        exp_map: ExplorationMap,
        state: ExplorationState,
    ) -> list[ExplorationEdge]:
        """回傳可見路徑。"""
        visible: list[ExplorationEdge] = []
        for edge in exp_map.edges:
            if edge.is_blocked:
                continue
            if edge.is_discovered or edge.id in state.discovered_edges:
                visible.append(edge)
        return visible
