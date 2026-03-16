"""CLI 入口——冒險劇本生成工具。

用法：
    uv run adventure-author new my_adventure
    uv run adventure-author build adventures/my_adventure/
    uv run adventure-author build-map adventures/my_adventure/maps/dungeon.md -o out.json
    uv run adventure-author validate adventures/my_adventure/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tot.tools.adventure_author.map_builder import build_map
from tot.tools.adventure_author.parser import parse_chapter, parse_map, parse_meta, parse_npc
from tot.tools.adventure_author.scaffold import create_adventure
from tot.tools.adventure_author.script_builder import build_script


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    parser = argparse.ArgumentParser(
        prog="adventure-author",
        description="冒險劇本生成工具——Markdown → JSON",
    )
    sub = parser.add_subparsers(dest="command")

    # new
    new_parser = sub.add_parser("new", help="建立新冒險資料夾")
    new_parser.add_argument("adventure_id", help="冒險 ID（資料夾名稱）")
    new_parser.add_argument("--name", default="", help="冒險名稱（預設用 ID）")
    new_parser.add_argument(
        "--dir",
        default=".",
        help="父目錄（預設當前目錄）",
    )

    # build
    build_parser = sub.add_parser("build", help="編譯整個冒險資料夾")
    build_parser.add_argument("adventure_dir", help="冒險資料夾路徑")
    build_parser.add_argument(
        "-o",
        "--output",
        default="",
        help="輸出目錄（預設為冒險資料夾下的 output/）",
    )

    # build-map
    bm_parser = sub.add_parser("build-map", help="編譯單張地圖 MD")
    bm_parser.add_argument("map_md", help="地圖 MD 檔案路徑")
    bm_parser.add_argument("-o", "--output", default="", help="輸出 JSON 路徑")

    # validate
    val_parser = sub.add_parser("validate", help="驗證冒險資料夾（不輸出）")
    val_parser.add_argument("adventure_dir", help="冒險資料夾路徑")

    args = parser.parse_args(argv)

    if args.command == "new":
        return _cmd_new(args)
    if args.command == "build":
        return _cmd_build(args)
    if args.command == "build-map":
        return _cmd_build_map(args)
    if args.command == "validate":
        return _cmd_validate(args)

    parser.print_help()
    return 1


def _cmd_new(args: argparse.Namespace) -> int:
    """建立新冒險資料夾。"""
    base = Path(args.dir)
    root = create_adventure(base, args.adventure_id, args.name)
    print(f"✅ 建立冒險資料夾：{root}")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    """編譯整個冒險資料夾。"""
    adv_dir = Path(args.adventure_dir)
    if not adv_dir.is_dir():
        print(f"❌ 找不到資料夾：{adv_dir}", file=sys.stderr)
        return 1

    output_dir = Path(args.output) if args.output else adv_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    errors = []

    # 編譯地圖
    maps_dir = adv_dir / "maps"
    if maps_dir.is_dir():
        for md_file in sorted(maps_dir.glob("*.md")):
            try:
                ir = parse_map(md_file.read_text(encoding="utf-8"))
                result = build_map(ir)
                out_path = output_dir / f"{result['id']}.json"
                out_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"  📍 地圖：{md_file.name} → {out_path.name}")
            except Exception as e:
                errors.append(f"地圖 {md_file.name}: {e}")

    # 編譯劇本
    try:
        meta_dict, initial_flags = _load_meta(adv_dir)
        npcs = _load_npcs(adv_dir)
        chapters = _load_chapters(adv_dir)
        result = build_script(meta_dict, initial_flags, npcs, chapters)
        out_path = output_dir / f"{result['id']}.json"
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  📜 劇本：{out_path.name}")
    except Exception as e:
        errors.append(f"劇本: {e}")

    if errors:
        print("\n❌ 錯誤：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"\n✅ 編譯完成，輸出到：{output_dir}")
    return 0


def _cmd_build_map(args: argparse.Namespace) -> int:
    """編譯單張地圖。"""
    md_path = Path(args.map_md)
    if not md_path.is_file():
        print(f"❌ 找不到檔案：{md_path}", file=sys.stderr)
        return 1

    try:
        ir = parse_map(md_path.read_text(encoding="utf-8"))
        result = build_map(ir)
    except Exception as e:
        print(f"❌ 解析錯誤：{e}", file=sys.stderr)
        return 1

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"✅ {md_path.name} → {out_path}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """驗證冒險資料夾。"""
    from tot.models.adventure import AdventureScript
    from tot.models.exploration import ExplorationMap

    adv_dir = Path(args.adventure_dir)
    if not adv_dir.is_dir():
        print(f"❌ 找不到資料夾：{adv_dir}", file=sys.stderr)
        return 1

    errors = []

    # 驗證地圖
    maps_dir = adv_dir / "maps"
    if maps_dir.is_dir():
        for md_file in sorted(maps_dir.glob("*.md")):
            try:
                ir = parse_map(md_file.read_text(encoding="utf-8"))
                result = build_map(ir)
                ExplorationMap.model_validate(result)
                print(f"  ✅ 地圖：{md_file.name}")
            except Exception as e:
                errors.append(f"地圖 {md_file.name}: {e}")
                print(f"  ❌ 地圖：{md_file.name} — {e}")

    # 驗證劇本
    try:
        meta_dict, initial_flags = _load_meta(adv_dir)
        npcs = _load_npcs(adv_dir)
        chapters = _load_chapters(adv_dir)
        result = build_script(meta_dict, initial_flags, npcs, chapters)
        AdventureScript.model_validate(result)
        print(f"  ✅ 劇本：{meta_dict.get('id', '?')}")
    except Exception as e:
        errors.append(f"劇本: {e}")
        print(f"  ❌ 劇本：{e}")

    if errors:
        return 1

    print("\n✅ 所有檢查通過")
    return 0


# ── 共用載入函式 ──────────────────────────────────────────


def _load_meta(adv_dir: Path) -> tuple[dict[str, str], dict[str, int]]:
    meta_path = adv_dir / "_meta.md"
    if meta_path.exists():
        return parse_meta(meta_path.read_text(encoding="utf-8"))
    return {}, {}


def _load_npcs(adv_dir: Path) -> list:
    from tot.tools.adventure_author.ir import NpcIR

    npcs_dir = adv_dir / "npcs"
    result: list[NpcIR] = []
    if npcs_dir.is_dir():
        for md_file in sorted(npcs_dir.glob("*.md")):
            npc = parse_npc(md_file.read_text(encoding="utf-8"))
            result.append(npc)
    return result


def _load_chapters(adv_dir: Path) -> list:
    from tot.tools.adventure_author.ir import ChapterIR

    chapters_dir = adv_dir / "chapters"
    result: list[ChapterIR] = []
    if chapters_dir.is_dir():
        for md_file in sorted(chapters_dir.glob("*.md")):
            chapter = parse_chapter(md_file.read_text(encoding="utf-8"))
            result.append(chapter)
    return result


if __name__ == "__main__":
    sys.exit(main())
