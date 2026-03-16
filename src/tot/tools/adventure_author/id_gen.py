"""名稱 → ID 轉換。

ASCII 名稱自動 slugify（"Forest Path" → "forest_path"）。
中文名需用 #explicit_id 標註，否則報錯。
"""

from __future__ import annotations

import re
import unicodedata


def slugify(name: str) -> str:
    """將名稱轉為 snake_case ID。

    只保留 ASCII 字母、數字、底線。空格和連字號轉為底線。
    連續底線合併為一個，頭尾底線去除。

    >>> slugify("Forest Path")
    'forest_path'
    >>> slugify("cave_entrance")
    'cave_entrance'
    >>> slugify("Guard Room #2")
    'guard_room_2'
    """
    # NFKD 正規化，移除 combining marks（accent 等）
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    # 非字母數字轉底線
    text = re.sub(r"[^a-zA-Z0-9]", "_", text)
    # 連續底線合併
    text = re.sub(r"_+", "_", text)
    return text.strip("_").lower()


def has_cjk(text: str) -> bool:
    """檢查字串是否含有 CJK 字元（Lo = Letter, other）。"""
    return any(unicodedata.category(ch).startswith("Lo") for ch in text)


def name_to_id(name: str, explicit_id: str | None = None) -> str:
    """將名稱轉為 ID。

    如果有 explicit_id，直接使用（去頭尾空白）。
    否則用 slugify。如果名稱含 CJK 字元且無 explicit_id，拋出 ValueError。

    >>> name_to_id("Forest Path")
    'forest_path'
    >>> name_to_id("松溪村", "pinebrook_village")
    'pinebrook_village'
    """
    if explicit_id:
        return explicit_id.strip()

    if has_cjk(name):
        msg = f"中文名稱 {name!r} 需要用 #id 標註 ID"
        raise ValueError(msg)

    result = slugify(name)
    if not result:
        msg = f"名稱 {name!r} 無法轉換為有效 ID"
        raise ValueError(msg)

    return result


def parse_heading_id(heading: str) -> tuple[str, str | None]:
    """從 heading 文字解析名稱和 #id。

    >>> parse_heading_id("Forest Path #forest_path")
    ('Forest Path', 'forest_path')
    >>> parse_heading_id("洞穴入口 #cave_entrance")
    ('洞穴入口', 'cave_entrance')
    >>> parse_heading_id("Guard Room")
    ('Guard Room', None)
    """
    match = re.search(r"\s+#(\S+)\s*$", heading)
    if match:
        name = heading[: match.start()].strip()
        explicit_id = match.group(1)
        return name, explicit_id
    return heading.strip(), None
