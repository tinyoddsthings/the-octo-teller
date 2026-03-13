# 空間戰鬥幾何決策紀錄

> **版本** v1.0 | 2026-03-13
> **相關文件**：[`bone-engine-v2-design.md`](bone-engine-v2-design.md) §8 Phase D

## 1. 文件目的

記錄 5 項空間/戰鬥幾何架構決策。每項以 **現況→分析→選定方案→影響** 格式呈現，
作為 Bone Engine 空間系統的架構決策紀錄（ADR）。

---

## 2. ADR-1：掩蔽判定射線模型（Cover Ray Model）

**優先序：HIGH**

### 2.1 D&D 5e 規則原文

> **DMG Cover Rules（2024 版摘要）**：
> 從攻擊者身體的**任一角落（corner）**到目標身體的**每一個角落**畫射線。
> - **半掩蔽（Half Cover, +2 AC）**：至少一條射線被阻擋
> - **3/4 掩蔽（Three-Quarters Cover, +5 AC）**：大部分射線被阻擋
> - **全掩蔽（Total Cover）**：所有射線被阻擋（無法被直接瞄準）
>
> 關鍵：判定基於**角對角（corner-to-corner）**射線數量，而非中心對中心。

### 2.2 現況分析

目前實作（`spatial.py:408` `determine_cover()`）使用**單條中心→中心射線**搭配障礙物計數：

```python
# spatial.py:408-442 — 現行實作
def determine_cover(attacker, target, map_state) -> CoverType:
    # 單射線：attacker.center → target.center
    for ob in obstacles:
        if segment_aabb_intersect(attacker, target, ob):
            blocking_count += 1
    # 判定：1 個障礙 = HALF，2+ = THREE_QUARTERS
```

**問題**：
1. 中心對中心無法區分「剛好被角落遮住」與「完全暴露」
2. 障礙物計數法（1=HALF, 2+=3/4）是近似值，非規則RAW
3. `bone-engine-v2-design.md` §8 D-1 原方案用 Bresenham 格線路徑 + Prop 掩護查表——仍是**單射線**思維

### 2.3 連續空間的 Corner-Ray 演算法

在連續空間中，以 AABB（Axis-Aligned Bounding Box）代表生物佔位：

```python
# 虛擬碼：Corner-Ray 掩蔽判定
def determine_cover_corner_ray(
    attacker_aabb: AABB,
    target_aabb: AABB,
    obstacles: list[AABB],
    actors: list[Actor],
) -> CoverResult:
    """攻擊者 4 角 → 目標 4 角 = 16 條射線。

    取「最佳角落」：攻擊者選擇通過射線最多的那個角落。
    D&D 規則允許攻擊者選最有利角落，所以取 max。
    """
    attacker_corners = attacker_aabb.corners()  # 4 個 (x, y)
    target_corners = target_aabb.corners()      # 4 個 (x, y)

    best_clear = 0  # 攻擊者最佳角落的通過數

    for ac in attacker_corners:
        clear = 0
        for tc in target_corners:
            blocked = False
            for ob in obstacles:
                if segment_aabb_intersect(ac, tc, ob):
                    blocked = True
                    break
            if not blocked:
                clear += 1
        best_clear = max(best_clear, clear)

    # 判定規則
    if best_clear == 4:
        return CoverResult(CoverType.NONE)
    elif best_clear == 3:
        return CoverResult(CoverType.HALF)       # +2 AC
    elif best_clear >= 1:
        return CoverResult(CoverType.THREE_QUARTERS)  # +5 AC
    else:
        return CoverResult(CoverType.TOTAL)       # 無法瞄準
```

### 2.4 選定方案：Corner-Ray 取代單射線+計數法

| 項目 | 決策 |
|------|------|
| **LoS（視線判定）** | 維持 `has_line_of_sight()` center→center 單射線（二元判定） |
| **Cover（掩蔽判定）** | `determine_cover()` 改為 4→4 corner-ray（梯度判定） |
| **效能** | 16 rays × N obstacles ≈ 800 tests（N~50 時），Liang-Barsky 單次 ~10ns → <10μs，可忽略 |

### 2.5 與 bone-engine-v2-design.md §8 的關係

- **D-1 演算法修正**：原方案的 Bresenham 格線路徑不再適用（已無格線），改為 Corner-Ray
- **CoverResult / D-2 / D-3 不變**：`CoverResult` 資料結構、投射物打掩護、測試計畫維持原設計
- D-1 的 Prop `cover_bonus` 整合仍有效——Corner-Ray 檢測時一併收集提供掩蔽的 Prop

### 2.6 影響範圍

| 檔案 | 變動 |
|------|------|
| `spatial.py` `determine_cover()` | 重寫為 Corner-Ray（~60 行） |
| `geometry.py` | 新增 `AABB.corners()` method（~5 行） |
| `tests/test_spatial.py` | 更新掩蔽測試用例 |
| `tests/test_cover_v2.py` | 新建（依 §8 D-3 計畫） |
| `docs/bone-engine-v2-design.md` §8 D-1 | 加前向引用 |

---

## 3. ADR-2：動態路徑障礙——友軍/敵軍/死亡生物

**優先序：LOW**

### 3.1 現況分析（已大半實作）

| 功能 | 狀態 | 位置 |
|------|------|------|
| `can_traverse()` 敵/友區分 | ✅ 已實作 | `spatial.py` |
| `find_path_to_range()` blocked/passable 分離 | ✅ 已實作 | `pathfinding.py:33` |
| passable cost ×2 | ✅ 已實作 | `pathfinding.py` |
| `build_actor_lists()` 過濾死亡 Actor | ✅ 已實作 | `pathfinding.py` |

### 3.2 殘餘問題

1. `pathfinding.py` 本身**不做防禦性過濾**——依賴呼叫者傳入正確的 `blocked`/`passable` 集合
2. 邊級 cost 粒度：整條 Visibility Graph 邊 ×2（passable Actor 位於邊上時），非精確段落計算
   - 實務影響極小：Actor 佔位直徑 ~1.5m，邊通常遠長於此

### 3.3 選定方案：維持現狀 + docstring 補強

- `build_actor_lists()` 是唯一入口，已正確過濾死亡 Actor
- `find_path_to_range()` docstring 加一行提示：「呼叫者須先透過 `build_actor_lists()` 取得正確的 blocked/passable 集合」
- 不新增程式碼，僅文件化

---

## 4. ADR-2.5：強制位移與路徑碰撞檢測（Forced Movement CCD）

**優先序：MEDIUM**

### 4.1 現況分析

| 元件 | 行為 | 風險 |
|------|------|------|
| `move_entity()` (spatial.py:299) | 只檢查終點 `is_position_clear()` | 正常移動安全（A* 保證路徑繞牆） |
| `attempt_shove()` (combat.py:1043) | push 效果直接算終點座標（+1.5m 方向向量） | ⚠️ 終點可能穿牆 |
| 法術強制位移（雷鳴波等） | 尚未實作，未來會直接指定位移向量 | ⚠️ 同上 |

**核心問題**：正常移動靠 A* 路徑規劃保證不穿牆，但**強制位移繞過路徑規劃**，
直接計算位移終點——如果起點→終點之間有牆壁 AABB，生物會穿牆。

### 4.2 選定方案：move_entity 加 forced 參數

```python
def move_entity(
    actor, tx, ty, map_state, speed_remaining,
    *, forced: bool = False,  # 新增
    allies=None, mover_size=Size.MEDIUM,
) -> MoveResult:
    """
    forced=True 時：
    1. 跳過速度/OA/困難地形檢查（強制位移不觸發借機攻擊）
    2. 用 segment_aabb_intersect() 掃描起點→終點路徑
    3. 碰到牆壁 → 找 Liang-Barsky 最近交點 t_enter → 停在牆前
       stop_x = ox + (tx - ox) * (t_enter - epsilon)
       stop_y = oy + (ty - oy) * (t_enter - epsilon)
    4. 可選：撞牆傷害（D&D 5e 可選規則，每 10 呎 1d6）
    """
```

**設計要點**：
- 複用現有 Liang-Barsky（`geometry.py:39` `segment_aabb_intersect()`），不需新演算法
- 需要擴充 `segment_aabb_intersect()` 回傳 `t_enter` 參數（目前只回傳 bool）
- 新增 `segment_aabb_intersect_t()` 或讓原函式回傳 `Optional[float]`

### 4.3 影響範圍

| 檔案 | 變動 |
|------|------|
| `geometry.py` | 新增 `segment_aabb_nearest_t()` 回傳最近交點 t 值（~15 行） |
| `spatial.py` `move_entity()` | +~15 行路徑檢查（`forced=True` 分支） |
| `combat.py` `attempt_shove()` | 呼叫 `move_entity()` 時加 `forced=True` |
| 未來法術強制位移 | 統一走 `forced=True` |
| `tests/test_spatial.py` | 新增強制位移穿牆測試 |

---

## 5. ADR-3：Braille 長寬比（TUI Aspect Ratio）

**優先序：NONE（已驗證非問題）**

### 5.1 分析

終端字元的典型長寬比約為 **1:2**（寬:高），而 Unicode Braille 字元提供 **2×4 dot** 矩陣：

```
每個字元 = 2 dots 寬 × 4 dots 高
像素比 = (字元寬 / 2) : (字元高 / 4)
       = (W/2) : (H/4)
       = (W/2) : (2W/4)     # 因為 H ≈ 2W
       = (W/2) : (W/2)
       = 1 : 1              # 近似正方形！
```

Braille 的 2×4 矩陣**天然補償**了終端字元的 ~2:1 長寬比，使得每個 dot 近似正方形。
實際差異 ~10%（取決於字型），在戰術地圖顯示中可忽略。

### 5.2 選定方案：不改動，記錄為已驗證非問題

- 目前 `canvas.py` 的 `BrailleMapCanvas` 已正確運作
- 未來可加 `aspect_correction: float` 參數微調，但不主動實作

### 5.3 驗證方式

目視渲染 3m×3m 正方形房間，確認 Braille 輸出接近正方形。

---

## 6. ADR-4：距離計算哲學——歐幾里得 vs 格線

**優先序：NONE（決策紀錄，無程式碼變動）**

### 6.1 三種方案比較

| 方案 | 公式 | 5 呎斜走 | 優點 | 缺點 |
|------|------|----------|------|------|
| **歐氏距離** | √(Δx²+Δy²) | 7.07 ft | 精確、與連續空間一致 | 偏離 D&D 桌遊體驗 |
| **切比雪夫** | max(\|Δx\|,\|Δy\|) | 5 ft | 簡單、D&D 4e/基礎規則 | 斜走太便宜 |
| **5-10-5 交替** | 奇數斜走 5ft、偶數 10ft | ~7.5 ft 平均 | D&D 5e PHB 可選規則 | 需要追蹤奇偶狀態 |

### 6.2 選定方案：維持純歐氏距離

理由：
1. 與 2-S 連續空間重構方向一致（已無格線，切比雪夫/5-10-5 失去意義）
2. Bone Engine 內部全部使用公尺 float 計算
3. UI 層做 5 呎 snap 顯示（如「30 呎」而非「9.14 公尺」）供玩家參考

### 6.3 呎↔公尺對照表

| D&D（呎） | 公尺 | 常見用途 |
|-----------|------|----------|
| 5 ft | 1.5 m | 近戰射程、格寬 |
| 10 ft | 3.0 m | 長柄武器射程 |
| 15 ft | 4.5 m | Cone 基礎長度 |
| 20 ft | 6.0 m | 球形 AoE 半徑 |
| 30 ft | 9.0 m | 基礎移動速度 |
| 60 ft | 18.0 m | 短弓射程 |
| 120 ft | 36.0 m | 多數法術射程 |
| 150 ft | 45.0 m | 長弓射程 |

### 6.4 對 D&D 忠實度的影響

歐氏距離在斜向移動上比 D&D 桌遊嚴格（7.07 ft vs 5 ft），但：
- 連續空間中玩家不會「走格線」，而是自由移動——斜走懲罰自然消失
- 30 呎移動速度（9m）在任何方向上都是 9m 半徑圓——比方格更直覺
- 射程判定更精確（60 ft 短弓不會因斜向多打 14 呎）

---

## 7. 總覽表

| ADR | 主題 | 優先序 | 程式碼變動 |
|-----|------|--------|-----------|
| ADR-1 | 掩蔽 Corner-Ray | **HIGH** | `determine_cover()` 重寫 |
| ADR-2 | 動態路徑障礙 | LOW | docstring only |
| ADR-2.5 | 強制位移路徑檢測 | **MEDIUM** | `move_entity()` +forced 參數 |
| ADR-3 | Braille 長寬比 | NONE | —（已驗證非問題） |
| ADR-4 | 距離計算哲學 | NONE | —（決策紀錄） |
