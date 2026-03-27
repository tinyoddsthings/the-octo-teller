"""角色卡 TUI 入口。

用法：
    uv run python -m tot.tui.character_sheet <path.json>
    uv run python -m tot.tui.character_sheet  # 列出已存角色選擇
"""

from __future__ import annotations

import sys
from pathlib import Path

from tot.tui.character_io import list_saved_characters, load_character
from tot.tui.character_sheet.app import CharacterSheetApp


def main() -> None:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"找不到角色卡檔案：{path}")
            sys.exit(1)
        char = load_character(path)
        app = CharacterSheetApp(char)
        app.run()
    else:
        # 列出已存角色讓使用者選擇
        saved = list_saved_characters()
        if not saved:
            print("沒有已存的角色卡。請先建角：")
            print("  uv run python -m tot.tui.character_creation")
            sys.exit(1)
        print("已存角色卡：")
        for i, p in enumerate(saved, 1):
            char = load_character(p)
            cls = list(char.class_levels.keys())[0] if char.class_levels else "?"
            lv = sum(char.class_levels.values())
            print(f"  {i}. {char.name}（{cls} Lv{lv}）— {p}")
        try:
            choice = int(input("\n選擇角色（輸入數字）：")) - 1
            if 0 <= choice < len(saved):
                char = load_character(saved[choice])
                app = CharacterSheetApp(char)
                app.run()
            else:
                print("無效選擇")
        except (ValueError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    main()
