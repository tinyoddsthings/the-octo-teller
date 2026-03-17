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
