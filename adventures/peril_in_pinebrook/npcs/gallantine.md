---
id: gallantine
name: 加侖丁
---

## 背景
description: 精瘦的年輕人，穿著深綠色的斗篷，隨手翻轉著一把小刀。眼神靈活，總是在觀察周圍的一切。
location: forest_trail_start
personality: 機靈、話少、有點嘴毒。不喜歡正面衝突，偏好偵查和暗中行動。
role: companion

## 常態對話 #gallantine_idle

> 「噓——你聯到了嗎？……哦，沒事，是松鼠。」

## 巡邏途中 #gallantine_patrol
condition: has:patrol_departed

> 加侖丁無聲無息地走在隊伍側翼，目光不停掃視樹叢間的陰影。
> 他忽然舉起手示意停步，側耳傾聽了一會兒，才放下手：「……沒事。繼續走。」

## 加侖丁自介 #companion_gallantine_intro
next: kole_ask_name

> 加侖丁靠在樹幹上，隨手翻轉著一把小刀：「加侖丁。眼睛比較利，耳朵比較尖。需要探路的時候叫我就行。」

## 銀龍回應 #troll_confident_response
next: troll_confident_evendorn

> 加侖丁嗤了一聲：「銀龍？那只是傳說而已。我在松溪住了這麼久，從沒見過什麼龍。」

## 擔心回應（加侖丁） #troll_worried_gallantine
next: troll_worried_kole

> 加侖丁摸了摸下巴：「不過都兩個月了，為什麼突然又有蹤跡？這不太對勁。」

## 懷疑回應（加侖丁） #troll_doubt_gallantine
next: troll_doubt_evendorn

> 加侖丁聳聳肩：「也不能排除是有人故意做出來嚇人的。」

## 好奇回應（加侖丁） #troll_curious_gallantine
next: troll_curious_kole

> 加侖丁翻了個白眼：「……謝謝你的精闢分析，岩炎。」

## 銀龍之謎（加侖丁） #troll_dragon_gallantine
next: troll_dragon_shalefire

> 「或者牠根本不存在。」

## 冰巨魔歷史（加侖丁） #troll_history_gallantine
next: troll_history_evendorn

> 「之後就有了例行巡邏制度——也就是我們現在在做的事。」

## 冰巨魔被驅趕（加侖丁） #troll_driven_gallantine
next: troll_driven_dm

> 加侖丁輕聲說：「比如一條龍？」

## 加侖丁攻擊 #e2_npc_gallantine
next: e2_npc_evendorn

> 加侖丁從側翼無聲地閃出，小刀精準地刺入搖搖欲墜的冰錐的裂縫中。冰錐發出一聲尖銳的碎裂聲，碎成一地冰渣。
> 「兩個了。」

## 知識檢定失敗 #e2_knowledge_fail
next: e2_dragon_runs

> 加侖丁蹲下來，用刀尖撥弄了一塊冰渣：「我聽說過……冰巨魔會製造這種東西來看守地盤。如果這裡有這些玩意兒，那冰巨魔——」
> 他抬頭看向洞穴深處。
> 「……可能就在裡面。」

sets_flag: icicle_knowledge

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 3：危險的巢穴 -->
<!-- ═══════════════════════════════════════════ -->

## 壁畫分析 #e3_gallantine_drawings
condition: has:encounter3_started

> 加侖丁湊近壁畫，用小刀的刀面反射火光仔細觀察。
> 「這些畫法很粗糙……不是人類或精靈的風格。」
> 他若有所思地摸了摸下巴。
> 「如果壁畫上畫的是冰巨魔，那牠們可能在這裡住了很長一段時間。」

## 歷史知識 #e3_gallantine_history
condition: has:e3_troll_cave_known

> 加侖丁點點頭：「我讀過相關記載——冰巨魔有在洞穴中建立據點的習性。牠們會在牆壁上留下壁畫記錄自己的活動。」
> 他環顧四周。
> 「如果這裡曾經是牠們的地盤，那更深處可能還有更多痕跡。小心點。」

## 攀爬觀察 #e3_gallantine_climb
condition: all:has:e3_cave_explored,not:e3_wall_climbed

> 加侖丁無聲地走到冰壁旁，手指輕觸壁面，尋找裂隙。
> 「有些地方冰層比較薄，下面是乾燥的岩石。」
> 他指了指幾個位置。
> 「踩那裡會比較穩。」

## 冰鏡觀察 #e3_gallantine_mirror
condition: all:has:e3_wall_climbed,not:e3_mirror_passed

> 加侖丁盯著冰鏡裡自己變成龍的倒影，一言不發。過了好一會兒他才開口：
> 「……有意思。這面冰不是自然形成的。有某種魔法在運作。」

## 冰道偵查 #e3_gallantine_slides
condition: all:has:e3_mirror_passed,not:e3_slides_done

> 加侖丁趴在峭壁邊緣，眼睛飛速掃過下方的滑道網絡。
> 「大部分滑道都是死路——要嘛撞上冰牆，要嘛經過那些鋒利的冰錐。」
> 他指了指其中一條。
> 「那條看起來弧度最緩，表面也最平滑。但不保證到底會怎樣。」

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 4：龍蛋與灼目之銀 -->
<!-- ═══════════════════════════════════════════ -->

## 加侖丁攻擊竊蛋獸 #e4_npc_gallantine
next: e4_npc_evendorn

> 加侖丁無聲地繞到竊蛋獸的背後，小刀精準地刺入了它的軟肋。生物嘶叫著轉身撲來，但加侖丁已經閃到了一邊。
> 「它們的皮比看起來軟。」

## 加侖丁觀察勞恩 #e4_gallantine_rorn
condition: all:has:e4_rorn_appeared,not:rorn_calmed

> 加侖丁一動不動地站著，眼睛卻在飛速轉動，觀察著銀龍的每一個細節。
> 他用極低的聲音說：「別輕舉妄動。」
> 一拍。
> 「我們連逃跑的機會都沒有。」

## 加侖丁尾聲 #e4_gallantine_epilogue
condition: has:rorn_calmed

> 加侖丁靠在洞壁上，難得地露出了一絲真誠的笑容。
> 「今天之前，我覺得銀龍的傳說只是故事。」
> 他看了看那三條在母親身邊嬉戲的幼龍。
> 「……我很高興自己是錯的。」
