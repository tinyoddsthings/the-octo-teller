"""角色卡 JSON 存讀模組。

存檔路徑：~/.tot/characters/<name>.json
"""

from __future__ import annotations

from pathlib import Path

from tot.models.creature import Character

# 預設存檔目錄
CHARACTERS_DIR = Path.home() / ".tot" / "characters"


def _ensure_dir() -> Path:
    """確保存檔目錄存在。"""
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    return CHARACTERS_DIR


def _safe_filename(name: str) -> str:
    """將角色名轉為安全檔名（保留中文，替換特殊字元）。"""
    # 替換檔案系統不允許的字元
    for ch in r'\/:"*?<>|':
        name = name.replace(ch, "_")
    return name.strip() or "unnamed"


def save_character(char: Character, path: Path | None = None) -> Path:
    """將角色存為 JSON 檔案。

    Args:
        char: 要存檔的角色。
        path: 自訂存檔路徑，若為 None 則使用預設路徑。

    Returns:
        實際存檔的 Path。
    """
    if path is None:
        _ensure_dir()
        filename = _safe_filename(char.name) + ".json"
        path = CHARACTERS_DIR / filename

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(char.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_character(path: Path) -> Character:
    """從 JSON 檔案讀取角色。

    Args:
        path: 角色卡 JSON 檔案路徑。

    Returns:
        Character 物件。

    Raises:
        FileNotFoundError: 檔案不存在。
        ValidationError: JSON 格式不符 Character schema。
    """
    return Character.model_validate_json(path.read_text(encoding="utf-8"))


def list_saved_characters() -> list[Path]:
    """列出所有已存檔的角色卡。

    Returns:
        按修改時間排序（最新在前）的 JSON 檔案路徑清單。
    """
    if not CHARACTERS_DIR.exists():
        return []
    paths = sorted(CHARACTERS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return paths
