---
id: shalefire
name: 岩炎
---

## 背景
description: 魁梧的年輕戰士，腰間配著一把磨得鋥亮的闊劍。說話直來直去，笑起來聲音很大。
location: forest_trail_start
personality: 豪爽、直率、好戰。嘴上愛逞強但其實很照顧同伴。
role: companion

## 常態對話 #shalefire_idle

> 「嘿，別走太慢！」

## 巡邏途中 #shalefire_patrol
condition: has:patrol_departed

> 岩炎一邊走一邊隨手揮舞闊劍砍斷路邊的枯枝。
> 「說真的，我倒希望今天能碰上點什麼。巡邏巡了這麼久，手都癢了。」

## 岩炎自介 #companion_shalefire_intro
condition: all:has:intro_started,not:companions_introduced
next: companion_evendorn_intro

> 岩炎率先開口，拍了拍腰間的闊劍：「我叫岩炎。打東西是我的專長，別的不多說了。」他咧嘴一笑。

## 擔心回應 #troll_worried_response
next: troll_worried_evendorn

> 岩炎用力點了點頭：「沒錯。上次冰巨魔出現的時候，據說毀了好幾個伐木營地。」

## 銀龍回應（岩炎） #troll_confident_shalefire
next: troll_confident_kole

> 「管他龍不龍的，冰巨魔可是真的。當年留下的爪痕到現在還在老磨坊的牆上呢。」

## 懷疑回應（岩炎） #troll_doubt_shalefire
next: troll_doubt_gallantine

> 「而且帶著霜。普通動物留不下那種痕跡。」

## 好奇回應（岩炎） #troll_curious_shalefire
next: troll_curious_gallantine

> 「簡單說，就是打起來很痛的大傢伙。」

## 巡邏注意事項（岩炎） #troll_precaution_shalefire

> 岩炎小聲嘟囔：「……雖然當英雄聽起來不錯。」

choices:
- **「明白，安全第一。」** #choice_end_precaution → kole_depart
  sets_flag: troll_discussed

## 銀龍之謎（岩炎） #troll_dragon_shalefire
next: troll_dragon_kole

> 「我寧可相信有條龍在保護我們。至少晚上睡覺比較安心。」

## 冰巨魔歷史（岩炎） #troll_history_shalefire
next: troll_history_gallantine

> 「當時村裡組了一支大隊，在山腳下設了埋伏。死了不少人，但總算把牠們趕回山裡去了。」

## 冰巨魔被驅趕（岩炎） #troll_driven_shalefire

> 岩炎握緊了劍柄：「不管怎樣，我們走了就知道了。」

choices:
- **「走吧，眼見為憑。」** #choice_end_driven → kole_depart
  sets_flag: troll_discussed

## 猜測是龍 #encounter1_guess_dragon
next: encounter1_identify_prompt

> 岩炎湊過來瞪大了眼：「龍？這小不點是龍？」
> 他蹲下身，好奇地盯著小龍。小龍嘶了一聲，朝他的手指咬了一口——完全不痛。

## 岩炎攻擊 #e2_npc_shalefire
next: e2_npc_gallantine

> 岩炎揮出闊劍，一刀將一隻冰錐從中劈開，碎冰四濺。「哈！脆得跟冰棒一樣！」
> 他順勢橫掃，闊劍的餘勢狠狠撞上第二隻冰錐的身體，將它打得搖搖欲墜。

## 隊友補刀 #e2_ally_finish
next: e2_victory

> 岩炎從背後一劍劈下：「接好了——」
> 冰錐從中間裂開，碎成一地。他轉頭朝你咧嘴笑：「下次自己來啊。」

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 3：危險的巢穴 -->
<!-- ═══════════════════════════════════════════ -->

## 壁畫反應 #e3_shalefire_drawings
condition: has:encounter3_started

> 岩炎瞇著眼看壁畫：「這些醜東西……看起來像是在慶祝什麼。」
> 他用手指在一幅壁畫上劃了一下，沾了一手灰。
> 「不管是誰畫的，品味夠差的。」

## 攀爬逞強 #e3_shalefire_climb
condition: all:has:e3_cave_explored,not:e3_wall_climbed

> 岩炎活動了一下手指，朝手心吐了口唾沫：「五十呎？小意思。看我的！」
> 他一把抓住冰壁上的凸起，開始往上爬。
> 闊劍在背後晃來晃去，好幾次差點敲到旁邊的人。

## 攀爬頂端 #e3_shalefire_rope
condition: has:e3_wall_climbed

> 岩炎趴在頂端，朝下面揮手：「快上來！我把繩子放下去——抓穩了！」

## 冰鏡驚嘆 #e3_shalefire_mirror
condition: all:has:e3_wall_climbed,not:e3_mirror_passed

> 岩炎看著冰鏡裡自己變成銀龍的模樣，眼睛瞪得老大。
> 「……我變成龍了？哈！看看這翅膀！比真的還威風！」
> 他高興了一秒，然後突然清醒過來。
> 「等等，這不對勁。」

## 冰道興奮 #e3_shalefire_slides
condition: all:has:e3_mirror_passed,not:e3_slides_done

> 岩炎站在峭壁邊緣，看著下面的冰道，臉上居然露出了興奮的表情。
> 「這……看起來挺好玩的啊！」
> 他注意到科爾隊長的眼神，馬上收斂了笑容。
> 「我是說——挺危險的。非常危險。」

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 4：龍蛋與灼目之銀 -->
<!-- ═══════════════════════════════════════════ -->

## 岩炎攻擊竊蛋獸 #e4_npc_shalefire
next: e4_npc_gallantine

> 岩炎一聲怒吼，闊劍高高舉起，重重劈向竊蛋獸！劍刃深深嵌入白色的身體，生物痛苦地嘶叫著被打退了好幾步。
> 「醜東西！離那些蛋遠點！」

## 岩炎怕龍 #e4_shalefire_rorn
condition: all:has:e4_rorn_appeared,not:rorn_calmed

> 岩炎的臉色瞬間變得煞白。他的手還握著闊劍，但劍尖已經不自覺地朝下了。
> 「……這、這就是傳說中的銀龍？」
> 他吞了吞口水。
> 「比我想像的大很多。非常多。」

## 岩炎尾聲 #e4_shalefire_epilogue
condition: has:rorn_calmed

> 岩炎盯著三條小龍搶食的場景，傻笑著。
> 「嘿——牠們打架的樣子跟我小時候一樣。」
> 他伸手想摸一條新出生的幼龍，被勞恩輕輕一個噴氣嚇得縮回了手。
> 「……好好好，不摸了。」
