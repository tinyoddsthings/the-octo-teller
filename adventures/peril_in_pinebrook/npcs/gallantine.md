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
