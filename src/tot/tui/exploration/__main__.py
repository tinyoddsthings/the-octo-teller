"""探索 TUI 入口點。

用法：
  uv run --extra tui python -m tot.tui.exploration [地圖名]

地圖名為 explore_demo.py 中 AVAILABLE_MAPS 的 key。
"""

import sys

from tot.tui.exploration.app import ExplorationTUI

map_key = sys.argv[1] if len(sys.argv) > 1 else None
app = ExplorationTUI(initial_map=map_key)
app.run()
