#!/usr/bin/env python3
"""
DnD Telegram Bot — 接 Claude Code CLI
"""
import os
import re
import json
import subprocess
import logging
import threading
import time
import asyncio as aio
from pathlib import Path
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# ── 路徑設定 ──────────────────────────────────────────
BASE = Path(__file__).parent
CLAUDE_MEMORY = Path.home() / ".claude/projects/-Users-cfh00997125/memory"
SAVE_FILE = CLAUDE_MEMORY / "dnd.md"
GLOSSARY_FILE = CLAUDE_MEMORY / "dnd_glossary.md"
DM_PROMPT_FILE = BASE / "dm_prompt.md"
DICE_SCRIPT = BASE / "tools" / "dice.sh"
DND_QUERY = BASE / "tools" / "dnd_query.py"
DND_MCP_PATH = Path.home() / "Tools" / "dnd-mcp"

# ── 對話歷史設定 ──────────────────────────────────────
HISTORY_FILE = BASE / "save" / "chat_history.json"
MAX_HISTORY_TURNS = 5
MAX_DM_REPLY_CHARS = 1500
chat_history: dict[str, list[dict]] = {}

# ── Telegram Bot Token ────────────────────────────────
BOT_TOKEN = "8696466871:AAFvEvBsJmZkxDWOZ_bqbkZc7tyitaL6iz4"

# ── 允許的 Telegram user ID（留空 = 不限制）──────────
ALLOWED_USERS: set[int] = set()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)


# ── 對話歷史管理 ──────────────────────────────────────

def load_history():
    global chat_history
    if HISTORY_FILE.exists():
        try:
            chat_history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            log.info(f"載入對話歷史：{len(chat_history)} 個聊天室")
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"載入歷史失敗：{e}")
            chat_history = {}


def save_history():
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(chat_history, ensure_ascii=False, indent=2), encoding="utf-8")
    except IOError as e:
        log.warning(f"儲存歷史失敗：{e}")


def add_history_turn(chat_id: str, user_msg: str, dm_reply: str):
    if chat_id not in chat_history:
        chat_history[chat_id] = []
    chat_history[chat_id].append({
        "user": user_msg[:500],
        "dm": dm_reply[:MAX_DM_REPLY_CHARS],
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    # 只保留最近 N 輪
    chat_history[chat_id] = chat_history[chat_id][-MAX_HISTORY_TURNS:]
    save_history()


def clear_history(chat_id: str):
    chat_history.pop(chat_id, None)
    save_history()


def roll_dice(expr: str) -> str:
    """呼叫 dice.sh 擲骰"""
    result = subprocess.run(
        ["bash", str(DICE_SCRIPT), expr],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def query_monster(name: str) -> str:
    """查怪物資料"""
    result = subprocess.run(
        ["uv", "run", "python", str(DND_QUERY), "monster", name],
        capture_output=True, text=True, cwd=str(DND_MCP_PATH)
    )
    return result.stdout.strip()[:2000]  # 限制長度


MCP_TOOLS_DESC = """
## 可用工具（需要時輸出指令，bot 會自動執行並把結果帶回）

- 查怪物：`[QUERY:monster:goblin]`（英文 index，如 goblin, bugbear, nothic, zombie）
- 查法術：`[QUERY:spell:fireball]`（英文 index，如 eldritch-blast, hex, fireball）
- 依 CR 列怪物：`[QUERY:monsters_by_cr:0:1]`（min_cr:max_cr）
- 生成寶藏：`[QUERY:treasure:3]`（challenge rating）
- 擲骰：`[DICE:1d20]`、`[DICE:2d6+3]`

查詢結果會自動附加在你的下一輪 context 裡。
""".strip()


def run_mcp_query(qtype: str, args: list[str]) -> str:
    """執行 dnd_query.py 查詢"""
    cmd = ["uv", "run", "python", str(DND_QUERY), qtype] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(DND_MCP_PATH), timeout=30)
    return result.stdout.strip()


def build_prompt(user_message: str, mcp_results: str = "", history: list[dict] = None) -> str:
    """組合送給 Claude 的完整 prompt"""
    dm_prompt = DM_PROMPT_FILE.read_text(encoding="utf-8")
    save = SAVE_FILE.read_text(encoding="utf-8")
    glossary = GLOSSARY_FILE.read_text(encoding="utf-8")

    # 對話歷史段落
    history_section = ""
    if history:
        lines = []
        for i, turn in enumerate(history, 1):
            lines.append(f"**玩家（Turn {i}）：** {turn['user']}")
            lines.append(f"**DM：** {turn['dm']}")
        history_section = f"\n---\n\n# 近期對話紀錄\n\n" + "\n\n".join(lines) + "\n"

    # MCP 查詢結果段落
    if mcp_results:
        mcp_section = (
            f"\n---\n\n# 工具查詢結果\n\n"
            f"以下是你請求的查詢結果，請直接使用這些資料回覆玩家，不要再輸出 `[QUERY:]` 指令。\n\n"
            f"{mcp_results}\n"
        )
    else:
        mcp_section = ""

    return f"""{dm_prompt}

---

{MCP_TOOLS_DESC}

---

# 名詞對照表（所有專有名詞必須使用此表）

{glossary}

---

# 當前存檔

{save}
{history_section}{mcp_section}
---

# 玩家訊息

{user_message}
"""


def parse_dice_commands(text: str) -> str:
    """把回覆中的 [DICE:...] 換成實際骰子結果"""
    def replace_dice(m):
        expr = m.group(1)
        result = roll_dice(expr)
        return result

    return re.sub(r'\[DICE:([^\]]+)\]', replace_dice, text)


def parse_save_update(text: str) -> tuple[str, str | None]:
    """
    從回覆中提取 [SAVE_UPDATE]...[/SAVE_UPDATE]
    回傳 (cleaned_text, save_update_content)
    """
    pattern = r'\[SAVE_UPDATE\](.*?)\[/SAVE_UPDATE\]'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        update_content = match.group(1).strip()
        cleaned = re.sub(pattern, '', text, flags=re.DOTALL).strip()
        return cleaned, update_content
    return text, None


def parse_query_commands(text: str) -> str:
    """把 [QUERY:type:args] 換成查詢結果"""
    def replace_query(m):
        parts = m.group(0)[1:-1].split(":")  # 去掉 [ ]
        qtype = parts[1]
        args = parts[2:]
        result = run_mcp_query(qtype, args)
        return f"\n📖 [{qtype}: {' '.join(args)}]\n{result}\n"

    return re.sub(r'\[QUERY:[^\]]+\]', replace_query, text)


def log_exchange(prompt: str, reply: str):
    """把 prompt 和 reply 寫進 log 檔"""
    log_path = CLAUDE_MEMORY / "claude_log.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    divider = "=" * 60
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{divider}\n")
        f.write(f"[{timestamp}] PROMPT\n")
        f.write(f"{divider}\n")
        f.write(prompt + "\n")
        f.write(f"\n{divider}\n")
        f.write(f"[{timestamp}] REPLY\n")
        f.write(f"{divider}\n")
        f.write(reply + "\n")


def call_claude(prompt: str) -> str:
    """呼叫 claude CLI，無限等待，每30秒回報進度"""
    result_box = {}
    start_time = time.time()

    def run():
        r = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions", "-p", prompt],
            capture_output=True, text=True, timeout=None,
            env={**os.environ, "CLAUDECODE": ""}
        )
        result_box["result"] = r

    t = threading.Thread(target=run, daemon=True)
    t.start()

    # 等待，每30秒通知一次（寫進 log）
    while t.is_alive():
        t.join(timeout=30)
        if t.is_alive():
            elapsed = int(time.time() - start_time)
            prompt_tokens = len(prompt) // 4  # 粗估
            log.info(f"⏳ Claude 仍在處理中... 已等待 {elapsed}s，prompt 約 {prompt_tokens} tokens")

    elapsed = int(time.time() - start_time)
    r = result_box.get("result")
    if r is None:
        return "❌ 執行錯誤"

    if r.returncode != 0:
        log.error(f"Claude error: {r.stderr[:500]}")
        reply = f"❌ Claude 回應失敗：{r.stderr[:200]}"
    else:
        reply = r.stdout.strip()

    prompt_tokens = len(prompt) // 4
    reply_tokens = len(reply) // 4
    log.info(f"✅ Claude 完成，耗時 {elapsed}s，prompt ~{prompt_tokens} tokens，reply ~{reply_tokens} tokens")
    log_exchange(prompt, reply)
    return reply


def update_save_from_diff(update_content: str):
    """用 SAVE_UPDATE 內容蓋寫存檔：先備份、寫 tmp、再搬過去"""
    tmp_file = SAVE_FILE.with_suffix(".md.tmp")
    bak_file = SAVE_FILE.with_suffix(".md.bak")
    log_path = CLAUDE_MEMORY / "update_log.txt"

    try:
        # 備份當前存檔
        if SAVE_FILE.exists():
            bak_file.write_text(SAVE_FILE.read_text(encoding="utf-8"), encoding="utf-8")

        # 寫入 tmp
        tmp_file.write_text(update_content, encoding="utf-8")

        # 搬到正式位置
        tmp_file.replace(SAVE_FILE)
        log.info(f"✅ 存檔已更新（備份在 {bak_file.name}）")
    except Exception as e:
        log.error(f"❌ 存檔更新失敗：{e}")

    # 記錄最近一次變更（覆寫，不 append）
    with open(log_path, "w", encoding="utf-8") as f:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{ts}] 最近一次存檔更新\n\n{update_content}\n")


def extract_queries(text: str) -> list[dict]:
    """從 Claude 回覆中提取 [QUERY:...] 指令（不執行）"""
    queries = []
    for m in re.finditer(r'\[QUERY:([^\]]+)\]', text):
        parts = m.group(1).split(":")
        queries.append({
            "type": parts[0],
            "args": parts[1:],
            "raw": m.group(0),
        })
    return queries


def execute_queries(queries: list[dict]) -> str:
    """執行所有查詢，回傳格式化結果字串"""
    results = []
    for q in queries:
        try:
            data = run_mcp_query(q["type"], q["args"])
            label = f"{q['type']}: {' '.join(q['args'])}"
            results.append(f"### {label}\n\n{data}")
        except Exception as e:
            results.append(f"### {q['raw']} — 查詢失敗：{e}")
    return "\n\n".join(results)


async def call_claude_with_progress(prompt: str, update: Update, label: str = "") -> str:
    """呼叫 Claude CLI，非同步等待並定期回報進度"""
    result_box = {}
    start_time = time.time()
    prefix = f"{label} " if label else ""

    def run():
        result_box["reply"] = call_claude(prompt)

    t = threading.Thread(target=run, daemon=True)
    t.start()

    while t.is_alive():
        t.join(timeout=15)
        if t.is_alive():
            elapsed = int(time.time() - start_time)
            await update.message.reply_text(f"⏳ {prefix}還在想... 已等待 {elapsed}s")

    return result_box.get("reply", "❌ 未知錯誤")


async def handle_newsession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """清除該聊天室的對話歷史"""
    chat_id = str(update.effective_chat.id)
    clear_history(chat_id)
    await update.message.reply_text("🔄 對話歷史已清除，開始新的冒險！")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    chat_id = str(update.effective_chat.id)

    # 白名單檢查
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授權")
        return

    user_text = update.message.text
    log.info(f"[{username}] {user_text[:80]}")

    # 取對話歷史
    history = chat_history.get(chat_id, [])

    # 第一次呼叫 Claude
    prompt = build_prompt(user_text, history=history)
    prompt_tokens = len(prompt) // 4
    await update.message.reply_text(f"🎲 DM 正在思考中... (prompt ~{prompt_tokens} tokens)")

    reply = await call_claude_with_progress(prompt, update)

    # QUERY 回饋迴路：偵測查詢指令 → 執行 → 帶結果再呼叫一次
    queries = extract_queries(reply)
    if queries:
        query_names = ", ".join(f"{q['type']}:{' '.join(q['args'])}" for q in queries)
        await update.message.reply_text(f"📖 偵測到查詢：{query_names}，正在取得資料...")

        mcp_results = execute_queries(queries)
        prompt2 = build_prompt(user_text, mcp_results=mcp_results, history=history)
        reply = await call_claude_with_progress(prompt2, update, label="(查詢後)")

    # 處理骰子指令
    reply = parse_dice_commands(reply)

    # Fallback：處理殘餘查詢指令（正常不該還有）
    reply = parse_query_commands(reply)

    # 提取存檔更新
    reply, save_update = parse_save_update(reply)

    if save_update:
        update_save_from_diff(save_update)

    # 存對話歷史（錯誤回覆不存）
    if not reply.startswith("❌"):
        add_history_turn(chat_id, user_text, reply)

    # 分段發送（Telegram 單則上限 4096 字，使用 Markdown）
    for i in range(0, len(reply), 4000):
        chunk = reply[i:i+4000]
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            # Markdown 解析失敗就純文字送
            await update.message.reply_text(chunk)


def main():
    log.info("🎲 DnD Bot 啟動中...")
    load_history()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("newsession", handle_newsession))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("✅ 監聽中，等待玩家訊息...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
