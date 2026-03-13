"""探索 TUI 入口點。

用法：uv run --extra tui python -m tot.tui.exploration
"""

from tot.tui.exploration.app import ExplorationTUI

app = ExplorationTUI()
app.run()
