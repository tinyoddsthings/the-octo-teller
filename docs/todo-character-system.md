# 角色系統實作 Todo

對應主 todo.md 的 Phase A-1 與 Phase C 部分項目。

---

## 模組 2：角色卡 JSON 匯出（先做，前置基礎）

> 小型（1 commit）| 無難點

- [ ] 新增 `src/tot/tui/character_io.py`
  - `save_character(char: Character, path: Path | None = None) -> Path`
    — `Character.model_dump_json()` → `~/.tot/characters/<name>.json`
  - `load_character(path: Path) -> Character`
    — `Character.model_validate_json()`
  - `list_saved_characters() -> list[Path]`
    — 列出 `~/.tot/characters/` 下所有 `.json`

---

## 模組 1：角色建造 TUI

> 中型（2–3 commits）| 難點：Textual wizard UX

### 1-A：Wizard Screen 骨架 + 步驟 1–3

- [ ] 新建 `src/tot/tui/character_creation.py`（`CharacterCreationScreen(Screen)`）
- [ ] Step 1 — 角色姓名輸入（`Input` widget）
- [ ] Step 2 — 背景選擇（`ListView`，列出常見背景）
- [ ] Step 3 — 種族選擇（`ListView`，列出常見種族）
- [ ] 步驟狀態列（顯示目前在哪步，已完成幾步）
- [ ] 接 `CharacterBuilder.set_name() / set_background() / set_species()`

### 1-B：步驟 4–6 + 確認 + 存檔

- [ ] Step 4 — 職業選擇（`ListView`，列出 CLASS_REGISTRY 全部職業）
- [ ] Step 5 — 屬性分配（標準陣列 / 購點，數值輸入表單）
  - 標準陣列：拖放或下拉將 `[15,14,13,12,10,8]` 分配給 6 項屬性
  - 購點法：每項屬性顯示目前點數與剩餘預算
- [ ] Step 6 — 技能選擇（`SelectionList`，依職業限制多選）
- [ ] 確認畫面 — 顯示所有選項摘要，「確認建角」按鈕
- [ ] 建角完成 → 呼叫 `CharacterBuilder.build()` + `save_character()`
- [ ] 建角完成後可回到主選單

---

## 模組 3：完整角色卡顯示

> 中型（2–3 commits）| 難點：資訊量大，可能需分頁

### 3-A：角色卡 Widget 主體

- [ ] 新建 `src/tot/tui/character_sheet.py`（`CharacterSheetScreen(Screen)`）
- [ ] 六大屬性區塊（屬性值 + modifier，格式：`STR 16 (+3)`）
- [ ] 基本資訊：HP / HP Max / AC / 速度 / 熟練加值 / 先攻加值
- [ ] 豁免加值列表（6 項，熟練項標 `★`）
- [ ] 技能列表（全 18 項技能 + 加值，熟練項標 `★`，專精標 `★★`）

### 3-B：裝備、法術、附加資訊

- [ ] 裝備欄：武器列表（名稱 / 傷害骰 / 攻擊加值）+ 物品欄
- [ ] 法術欄（有施法能力者才顯示）：
  - 法術欄位表（各環級剩餘/最大）
  - 已知法術 / 已準備法術列表
  - 法術 DC / 法術攻擊加值
- [ ] 生命骰 / 死亡豁免 / XP
- [ ] 鍵盤快捷鍵：遊戲中按 `C` 開啟，`Escape` 關閉

---

## 模組 4：升級系統（最複雜，最後做）

> 大型（5–8 commits）| 主要瓶頸：職業升級資料化

### 4-A：職業升級資料（前置）

- [ ] 設計職業升級表資料格式（Python dataclass 或 dict）
  - 每筆：`level`、`features`（特性名稱列表）、`asi`（是否有 ASI/Feat 選擇）
- [ ] 優先實作劇本用到的職業（而非全部 12 個）
  - 確認「危在松溪」劇本用了哪些職業後再填表
- [ ] 將各職業升級表加入 `ClassData`（或獨立 `CLASS_LEVEL_TABLE`）
  - 資料來源：`docs/2024_translate/phb/ch3_*.md`

### 4-B：升級邏輯核心

- [ ] `level_up(character: Character, choices: LevelUpChoices) -> Character`
  - HP 增加（取平均或擲骰，從 `choices` 取）
  - 熟練加值更新
  - 法術欄位更新（`get_spell_slots(class, new_level)`）
  - 套用職業特性（被動加值類）
  - `character.level += 1`
- [ ] `LevelUpChoices` dataclass
  - `hp_roll: int | None`（None = 取平均）
  - `asi_choice: ASIChoice | None`
  - `feat_choice: str | None`
  - `new_spells: list[str]`

### 4-C：ASI / 專長選擇

- [ ] `ASIChoice`：`+2` 單一屬性，或 `+1/+1` 兩項屬性
- [ ] 驗證：屬性值不超過 20
- [ ] 讀取 `docs/2024_translate/phb/ch5_feats.md` 建立可選專長清單（至少常見專長）
- [ ] `apply_asi(character, choice)` / `apply_feat(character, feat_name)`

### 4-D：升級 TUI 流程

- [ ] 新建 `src/tot/tui/level_up.py`（`LevelUpScreen(Screen)`）
- [ ] 升一級提示（顯示新等級、解鎖特性列表）
- [ ] HP 選擇：取平均 or 擲骰
- [ ] ASI/Feat 選擇 wizard（若此等級有 ASI）
- [ ] 法術選擇（若此等級可學新法術）
- [ ] 確認畫面 → 呼叫 `level_up()` + 存檔

---

## 建議執行順序

1. **模組 2** — 角色卡 JSON 匯出
2. **模組 1-A** — 建角 TUI 骨架（步驟 1–3）
3. **模組 1-B** — 建角 TUI 完整（步驟 4–6 + 確認）
4. **模組 3-A** — 角色卡顯示主體
5. **模組 3-B** — 角色卡裝備/法術欄
6. **模組 4-A** — 職業升級資料（先確認劇本用到哪些職業）
7. **模組 4-B/C/D** — 升級邏輯 + TUI

---

## 關鍵檔案參考

| 路徑 | 說明 |
|------|------|
| `src/tot/gremlins/bone_engine/character.py` | CharacterBuilder、CLASS_REGISTRY |
| `src/tot/models/creature.py` | Character model（不動） |
| `src/tot/tui/stats_panel.py` | TUI widget 樣板 |
| `docs/2024_translate/phb/ch3_*.md` | 職業升級資料來源 |
| `docs/2024_translate/phb/ch5_feats.md` | 專長資料 |
