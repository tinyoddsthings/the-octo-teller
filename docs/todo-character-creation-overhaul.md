# 建角 TUI 改造計畫

> 對應主 todo.md A-1，依 2024 PHB (5.5e) ch2/ch3/ch4/ch5/ch7 重寫建角流程
> 參考文件：`docs/2024_translate/phb/ch2_creating_a_character.md` + ch3~ch5, ch7

## 現有問題

1. 所有選項只顯示英文名，無中文、無說明
2. 2024 PHB 建角順序：**職業 → 起源（背景+種族）→ 屬性值 → 填入細節**，現有順序不對
3. 護甲類型不該由玩家選（由職業決定訓練）
4. 子職業 2024 PHB 大多 3 級才選，1 級建角不選
5. 屬性值只有手動輸入，缺標準陣列/點數購買/擲骰
6. 屬性輸入框太窄只看到一位數
7. 缺少背景專長顯示
8. 缺少起始裝備選擇
9. 缺少戲法與法術選擇（施法職業）
10. 缺少背景屬性調整（+2/+1 或 +1/+1/+1）
11. 確認畫面資訊太少，缺背景專長、裝備等
12. 開發模式：完成後應顯示角色卡 JSON 存放位置

## 改造後建角步驟（依 2024 PHB）

| 步驟 | 內容 | 對應 PHB |
|------|------|---------|
| 1 | 選擇職業 | ch2 §1 + ch3 |
| 2 | 選擇背景（顯示專長/技能/工具/裝備） | ch2 §2 + ch4 背景 |
| 3 | 選擇種族（含血統/先祖子選項） | ch2 §2 + ch4 種族 |
| 4 | 屬性值（標準陣列/點數購買/擲骰 + 背景調整） | ch2 §3 |
| 5 | 技能選擇（職業技能） | ch2 §5 |
| 6 | 裝備選擇（背景+職業起始裝備） | ch2 §2, §5 |
| 7 | 戲法與法術（施法職業） | ch2 §5 + ch7 |
| 8 | 角色名稱 + 確認建角 | ch2 §5 |

---

## Phase CC-1：背景與種族資料層

> 目標：建立 16 背景 + 10 種族的結構化資料（中英文、說明、遊戲數值）
> 預計 2 commits

### CC-1a：背景資料結構 + 16 背景完整資料

- [ ] 新建 `src/tot/data/origins.py`
- [ ] `BackgroundData` dataclass：
  - `id: str`（英文 key）
  - `name_zh: str`（中文名）
  - `name_en: str`（英文名）
  - `description: str`（1~2 句中文說明）
  - `ability_tags: list[Ability]`（三項屬性，玩家從中選 +2/+1 或各 +1）
  - `feat: str`（起源專長名稱）
  - `skill_proficiencies: list[Skill]`（2 項固定技能）
  - `tool_proficiency: str`（工具名稱）
  - `equipment_a: str`（裝備選項 A 描述）
  - `equipment_b: str`（裝備選項 B = "50 GP"）
- [ ] `BACKGROUND_REGISTRY: dict[str, BackgroundData]` — 填入 16 背景完整資料
- [ ] 來源：`ch4_character_origins.md` 背景段落

### CC-1b：種族資料結構 + 10 種族完整資料

- [ ] `SpeciesData` dataclass：
  - `id: str`
  - `name_zh: str` / `name_en: str`
  - `description: str`（1~2 句）
  - `size: str`（"中型" / "小型" / "中型或小型"）
  - `speed: str`（"9m" 等）
  - `traits: list[str]`（特性名稱清單，如 ["暗視", "矮人韌性", ...]）
  - `traits_description: str`（特性的簡要說明文字）
  - `has_lineage_choice: bool`（是否有血統/先祖子選項）
  - `lineage_options: list[LineageOption]`（子選項，如精靈的卓爾/高等/木精靈）
- [ ] `LineageOption` dataclass：`id`, `name_zh`, `name_en`, `description`
- [ ] `SPECIES_REGISTRY: dict[str, SpeciesData]` — 填入 10 種族
- [ ] 來源：`ch4_character_origins.md` 種族段落

---

## Phase CC-2：職業資料擴充 + 起源專長

> 目標：擴充 CLASS_REGISTRY 加入中文名/說明/護甲訓練/裝備/戲法法術，建立起源專長資料
> 預計 2 commits

### CC-2a：職業資料擴充

- [ ] 擴充 `ClassData` 或新建 `ClassDisplayData`：
  - `name_zh: str`（中文名）
  - `description: str`（1~2 句）
  - `complexity: str`（低/中等/高）
  - `armor_training: list[str]`（如 ["輕甲", "中甲", "盾牌"]）
  - `weapon_training: list[str]`
  - `equipment_a: str` / `equipment_b: str`（起始裝備選項）
  - `num_cantrips: int`（1 級戲法數量，非施法者為 0）
  - `num_prepared_spells: int`（1 級備妥法術數量）
  - `cantrip_list: list[str]`（可選戲法清單）
  - `spell_list_1: list[str]`（1 環可選法術清單）
- [ ] 填入 12 職業的完整資料
- [ ] 來源：`ch3_*.md`（12 個職業文件）

### CC-2b：起源專長資料

- [ ] 新建 `src/tot/data/feats.py`
- [ ] `FeatData` dataclass：
  - `id: str`
  - `name_zh: str` / `name_en: str`
  - `category: str`（"起源" / "通用" / "戰鬥風格" / "史詩恩賜"）
  - `description: str`（完整效果說明，中文）
  - `has_spell_choice: bool`（如 Magic Initiate 需要選戲法/法術）
- [ ] `FEAT_REGISTRY: dict[str, FeatData]` — 至少填入全部 8 個起源專長
- [ ] 來源：`ch5_feats.md`

---

## Phase CC-3：TUI 重寫 — 步驟 1~3（職業、背景、種族）

> 目標：用新資料重寫前三步，全中文 + 詳細說明
> 預計 2 commits

### CC-3a：TUI 骨架重構 + 步驟 1 職業選擇

- [ ] 重寫 `app.py` 的 `_data` 結構，擴充欄位（feat, equipment, cantrips, spells 等）
- [ ] 步驟數量改為 8 步，更新 `STEP_TITLES`
- [ ] Step 1 — 職業選擇：
  - RadioSet 顯示「中文名（英文名）— 說明」
  - 選中後右側預覽面板顯示該職業詳細資訊（核心能力、生命骰、護甲/武器訓練、複雜度）
- [ ] 移除護甲類型選項、移除子職業選項（1 級不選）

### CC-3b：步驟 2 背景 + 步驟 3 種族

- [ ] Step 2 — 背景選擇：
  - RadioSet 顯示「中文名（英文名）— 說明」
  - 選中後右側預覽顯示：專長、技能熟練、工具熟練、裝備選項、可調整屬性
- [ ] Step 3 — 種族選擇：
  - RadioSet 顯示「中文名（英文名）— 說明」
  - 選中後右側預覽顯示：體型、速度、特性列表
  - 有血統子選項的種族（精靈、侏儒、龍裔、哥利雅、提夫林、神裔）：
    顯示子選項 RadioSet 讓玩家選擇血統/先祖

---

## Phase CC-4：TUI 重寫 — 步驟 4 屬性值

> 目標：三種屬性值生成方式 + 背景屬性調整
> 預計 2 commits

### CC-4a：屬性值生成 — 三種方式

- [ ] Step 4 上半：選擇生成方式（RadioSet）
  - **標準陣列**：顯示 `[15, 14, 13, 12, 10, 8]`，用 6 個下拉選單分配到 6 項屬性
    - 若已選職業，顯示該職業建議分配（ch2 標準陣列建議表）
  - **點數購買**：27 點預算，每項屬性有 +/- 按鈕（8~15），即時顯示剩餘點數和花費
  - **擲骰**：6 組 4d6 取高 3，自動擲出結果，玩家用下拉分配
- [ ] 修正輸入框寬度問題（改用下拉/按鈕取代 Input widget）
- [ ] 右側預覽即時顯示各屬性值和修正值

### CC-4b：背景屬性調整

- [ ] Step 4 下半：背景屬性調整
  - 顯示背景的 3 項可調屬性（如侍僧的 INT/WIS/CHA）
  - 玩家選擇：一項 +2 另一項 +1，或三項各 +1（RadioSet 選方案 + 指定）
  - 調整後的屬性值即時更新預覽
  - 驗證：調整後不超過 20

---

## Phase CC-5：TUI 重寫 — 步驟 5~6（技能、裝備）

> 目標：技能中文化 + 起始裝備選擇
> 預計 2 commits

### CC-5a：步驟 5 技能選擇

- [ ] Step 5 — 技能選擇：
  - 上方顯示背景已固定的 2 項技能（灰色不可改）
  - 下方 SelectionList 選職業技能（中文名 + 關聯屬性 + 加值預覽）
  - 若背景技能與職業技能重複，提示玩家可改選其他
  - 驗證選擇數量

### CC-5b：步驟 6 裝備選擇

- [ ] Step 6 — 裝備選擇：
  - 背景裝備：選項 A（具體裝備列表）或選項 B（50 GP）
  - 職業裝備：選項 A 或選項 B
  - 右側預覽顯示最終裝備清單
  - AC 根據實際裝備計算（非手動選護甲類型）

---

## Phase CC-6：TUI 重寫 — 步驟 7~8（法術、確認）

> 目標：施法職業的戲法/法術選擇 + 完整確認畫面
> 預計 2 commits

### CC-6a：步驟 7 戲法與法術

- [ ] Step 7 — 戲法與法術選擇（非施法職業跳過此步）：
  - 戲法：SelectionList，選 N 個（依職業，如法師選 3 個、魔導士選 2 個）
  - 中文顯示戲法名稱 + 簡述
  - 1 環備妥法術：SelectionList，選 N 個（依職業的 1 級備妥數量）
  - 中文顯示法術名稱 + 環級 + 簡述
- [ ] 背景專長法術（如 Magic Initiate 帶來的戲法/法術）也在此步顯示/選擇

### CC-6b：步驟 8 名稱 + 確認

- [ ] Step 8 — 角色名稱輸入 + 確認建角：
  - 上方：名稱輸入
  - 下方：完整角色卡摘要（比現有版本更詳細）：
    - 基本資訊：名稱、職業、背景、種族
    - 背景起源專長名稱及效果
    - 六項屬性值（含修正值 + 背景調整標記）
    - HP / AC / 先攻 / 被動感知 / 速度
    - 豁免熟練
    - 技能熟練列表（背景 + 職業，標示來源）
    - 工具熟練
    - 護甲/武器訓練
    - 裝備清單
    - 戲法與法術（如有）
    - 種族特性
  - 確認按鈕
- [ ] 確認後呼叫 `save_character()` 存檔
- [ ] 顯示角色卡 JSON 檔案路徑（開發模式）

---

## Phase CC-7：角色卡 I/O + 整合

> 目標：角色卡 JSON 存讀 + 主 TUI 入口整合
> 預計 1 commit

### CC-7a：角色卡 I/O + 入口整合

- [ ] 新建 `src/tot/tui/character_io.py`
  - `save_character(char, path=None) -> Path`
  - `load_character(path) -> Character`
  - `list_saved_characters() -> list[Path]`
- [ ] `__main__.py` 完成後印出角色卡 JSON 路徑
- [ ] `CharacterBuilder` 適配：移除 armor_type 手動設定（改由裝備決定）

---

## 建議執行順序

1. **CC-1a** — 背景資料
2. **CC-1b** — 種族資料
3. **CC-2a** — 職業資料擴充
4. **CC-2b** — 起源專長資料
5. **CC-3a** — TUI 骨架 + 步驟 1
6. **CC-3b** — TUI 步驟 2~3
7. **CC-4a** — 屬性值三種生成
8. **CC-4b** — 背景屬性調整
9. **CC-5a** — 技能選擇
10. **CC-5b** — 裝備選擇
11. **CC-6a** — 戲法與法術
12. **CC-6b** — 確認建角
13. **CC-7a** — I/O + 整合

---

## 關鍵檔案

| 路徑 | 說明 |
|------|------|
| `src/tot/data/origins.py` | 新建：背景+種族資料 |
| `src/tot/data/feats.py` | 新建：專長資料 |
| `src/tot/gremlins/bone_engine/character.py` | 擴充 ClassData / CLASS_REGISTRY |
| `src/tot/tui/character_creation/app.py` | 重寫：建角 TUI |
| `src/tot/tui/character_io.py` | 新建：角色卡 I/O |
| `docs/2024_translate/phb/ch2~5,7` | PHB 參考文件 |
