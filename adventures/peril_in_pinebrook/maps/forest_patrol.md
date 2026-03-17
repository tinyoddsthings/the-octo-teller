---
id: forest_patrol
name: 森林巡邏路線
scale: world
entry: forest_trail_start
---

## 林間小路 #forest_trail_start
type: landmark
description: 松溪村外的林間小路起點。陽光透過樹冠灑落，空氣中帶著松脂與泥土的氣息。巡邏隊在此集合出發。
ambient: 鳥鳴聲與遠處的伐木聲交織。偶爾傳來礦錘敲擊的迴響。
npcs: emmajeen_kole, shalefire, evendorn, gallantine

### → 前往密林深處 #trail_to_deep_forest
to: deep_forest
from: forest_trail_start
distance: 0.1day
terrain: 林間小徑
danger_level: 2

## 密林深處 #deep_forest
type: landmark
description: 林木漸密，陽光被厚重的枝葉遮擋。地面上落葉堆積，腳步聲被吞沒。科爾隊長突然停下腳步，舉起一隻手示意大家安靜。
ambient: 不尋常的寂靜。風中帶著一絲寒意。荊棘叢中隱約有窸窣聲。
npcs: emmajeen_kole, shalefire, evendorn, gallantine

items:
- 龍語翻譯書頁 #dragon_language_page | item | dc:0
  科爾隊長從《完全基本龍類指南》上撕下的一頁。記載了龍語和通用語的對照翻譯。

### → 前往山腳 #trail_to_mountain
to: mountain_approach
from: deep_forest
distance: 0.2day
terrain: 林間小徑
danger_level: 4

## 山腳林緣 #mountain_approach
type: landmark
description: 樹木漸稀，前方是一座巍峨的山峰。世界之脊山的積雪在陽光下閃閃發光。一個寬敞的洞穴入口就在前方不遠處。
ambient: 風變得刺骨。地面上散落著碎冰和結塊的雪花。
npcs: emmajeen_kole, shalefire, evendorn, gallantine

items:
- 舊皮包 #old_leather_pack | chest | dc:0
  一個被遺棄的舊皮背包，裡面有一包肉乾、五支火把、用來點火的鋼片和打火石，還有一個裝著 12 枚金幣的小包。
  value_gp: 12

encounter:
  enemies:
  - 活化冰錐 #living_icicle | CR:1/4
    冰錐和雪花組成的小型冰生物，長著尖銳的爪子。
    count: 5
  trigger: enter_node
  narration: 一片碎冰開始騷動起來。冰錐和雪花組成了小小的冰生物，長著嚇人的尖銳爪子。其中一個大叫著：「入侵者！狠狠地撕碎他們！」
  outcome: auto_win
  rewards:
  - 舊皮包 #loot_old_pack | value_gp: 12
  - 經驗值 #encounter2_xp | xp: 125
  sets_flag: icicles_defeated

### → 進入洞穴 #path_to_cave
to: dragon_cave
from: mountain_approach
distance: 0.1day
terrain: 洞穴入口
danger_level: 6

## 龍之洞穴 #dragon_cave
type: room
description: 洞穴入口寬敞，陽光灑進前段。深入後迅速變得黑暗，空氣中瀰漫著一股金屬般的氣味和淡淡的硫磺味。
ambient: 水滴聲在黑暗中迴盪。遠處似乎有微弱的呼吸聲。

<!-- 遭遇3：危險的巢穴（待後續提供） -->
