---
id: encounter2_icicle_battle
name: 遭遇 2——冰錐戰鬥（DM 旁白）
---

<!-- 遭遇 2 的 DM 旁白段，被 emmajeen_kole 的 next 引用進入 -->

## 龍寶寶嗅聞 #e2_dragon_sniff
speaker: dm
next: e2_cave_entrance

> 龍寶寶嗅著周圍的空氣，突然興奮起來，開始蹣跚著試圖靠近洞穴。牠辨認出了家的氣味。

## 進入洞穴 #e2_cave_entrance
speaker: dm
next: e2_icicle_attack

> 洞穴的入口十分寬敞，陽光灑進前段。不過深入後迅速變得黑暗，沒有任何辦法看到裡面有什麼。破碎的冰錐和結塊的雪花覆蓋了洞口的地面。

## 冰錐攻擊 #e2_icicle_attack
speaker: dm
next: e2_combat_tutorial

> 突然，一片碎冰開始騷動起來！冰錐和雪花迅速凝聚成五個小型冰生物，每個都長著嚇人的尖銳爪子。它們像活過來的冰雕，發出令人牙酸的刮擦聲。
>
> 其中一個最大的冰錐生物舉起爪子，發出尖銳的嘶吼：
> **「入侵者！狠狠地撕碎他們！」**
>
> 五隻活化冰錐朝你們撲來！

sets_flag: e2_combat_started

<!-- ═══════════════════════════════════════════ -->
<!-- 戰鬥教學 + 敘事戰鬥 -->
<!-- ═══════════════════════════════════════════ -->

## 戰鬥教學 #e2_combat_tutorial
speaker: dm

> 準備迎接你的第一場戰鬥！

choices:
- **「明白了，開始戰鬥！」** #choice_e2_fight → e2_initiative
- **「能再解釋一下嗎？」** #choice_e2_explain → e2_combat_explain

## 補充說明 #e2_combat_explain
speaker: dm
next: e2_initiative

> **動作（Action）**：你每回合最重要的行動。通常用來攻擊、施放法術或使用物品。
> **附加動作（Bonus Action）**：某些職業特性或法術可以用附加動作使用——例如盜賊的「狡猾動作」。不是每回合都有。
> **移動（Movement）**：你可以在回合中移動一段距離。大多數角色每回合可以移動 30 呎（約 9 公尺）。你可以在動作前後分段移動。
> **法術欄位（Spell Slots）**：如果你是法系職業，施放法術會消耗法術欄位。戲法（0 環法術）不消耗欄位，可以無限使用。

## 先攻階段 #e2_initiative
speaker: dm
next: e2_npc_round

> 科爾隊長反應極快，闊劍已經出鞘：「所有人，戰鬥陣形！」
>
> 岩炎一聲怒吼，衝向最近的兩隻冰錐。加侖丁已經閃到側翼，小刀在手。埃文多恩握緊聖徽，嘴唇快速默念禱詞。
>
> 這些冰錐生物看似兇猛，但它們的動作僵硬、遲緩——你們的隊伍率先發動了攻擊！

## NPC 攻擊回合 #e2_npc_round
speaker: dm
next: e2_npc_shalefire

> 隊友們率先出手——

## 玩家回合 #e2_player_turn
speaker: dm

> 兩隻活化冰錐一隻在你正前方，另一隻正繞到你的側面。它們的冰爪在微光中閃著寒芒。

choices:
- **「近戰攻擊！衝上去砍它！」** #choice_e2_melee → e2_player_melee
- **「遠程攻擊！從這裡射它！」** #choice_e2_ranged → e2_player_ranged
- **「施放法術攻擊！」** #choice_e2_spell → e2_player_spell

## 近戰攻擊 #e2_player_melee
speaker: dm
next: e2_player_hit

> 你握緊武器，大步衝向最近的冰錐！一刀揮下——冰錐的身體從中裂開，碎冰飛濺！

## 遠程攻擊 #e2_player_ranged
speaker: dm
next: e2_player_hit

> 你瞄準前方的冰錐，拉弓——箭矢劃出一道弧線，精準地射穿冰錐的胸口！冰面上迸出蛛網般的裂痕。

## 法術攻擊 #e2_player_spell
speaker: dm
next: e2_player_hit

> 你集中精神，魔力匯聚在指尖，一道能量射向冰錐——正中目標！冰錐的表面瞬間佈滿裂紋。

## 玩家命中 #e2_player_hit
speaker: dm
next: e2_last_icicle_attack

> 冰錐轟然碎裂，冰渣飛濺！剩最後一隻了——但它沒有退縮，反而更加瘋狂地撲向你。

<!-- ═══════════════════════════════════════════ -->
<!-- 冰錐反擊（固定受傷） -->
<!-- ═══════════════════════════════════════════ -->

## 冰錐反擊 #e2_last_icicle_attack
speaker: dm
next: e2_player_hit_reaction

> 剩餘的冰錐發出尖銳的嘶吼，以不顧一切的氣勢撲來。其中一隻猛地瞬移——彷彿冰面上的滑行——直接出現在你面前！
>
> 它的冰爪劃過你的手臂！冰冷的疼痛瞬間蔓延。
>
> **你受到了 3 點揮砍傷害。**

## 玩家最後一擊 #e2_final_blow
speaker: dm
next: e2_victory

> 你怒吼一聲，猛力揮出攻擊。這一次，冰錐完全碎裂，冰渣飛散在空氣中，在陽光下化成水霧。

<!-- ═══════════════════════════════════════════ -->
<!-- 戰鬥結束 -->
<!-- ═══════════════════════════════════════════ -->

## 勝利 #e2_victory
speaker: dm

> 最後一隻活化冰錐碎裂倒地。洞穴入口重歸寂靜，只剩下地上散落的冰渣和你們急促的呼吸聲。
>
> 科爾隊長收起劍，環顧四周確認安全。「都解決了。大家還好嗎？」

sets_flag: icicles_defeated

choices:
- **「我受傷了，但還撐得住。」** #choice_e2_hurt → e2_search_prompt
- **「沒問題！再來幾個都行。」** #choice_e2_fine → e2_search_prompt

## 找到皮包 #e2_found_pack
speaker: dm
next: e2_divide_loot

> 你在洞穴入口的角落發現了一個舊皮背包，看起來已經在這裡很久了。打開一看，裡面有：
>
> 🎒 **一包肉乾**
> 🔥 **五支火把** + 鋼片和打火石
> 💰 **12 枚金幣**

## 分配寶藏 #e2_divide_loot
speaker: dm

> 你們可以自行分配這些物品。

choices:
- **「大家平分吧。」** #choice_e2_split → e2_heal_prompt
  sets_flag: loot_divided
- **「火把和打火石我先拿著，進洞穴會用到。」** #choice_e2_take_torch → e2_heal_prompt
  sets_flag: loot_divided

<!-- ═══════════════════════════════════════════ -->
<!-- 治療階段 -->
<!-- ═══════════════════════════════════════════ -->

## 治療完成 #e2_healed
speaker: dm
next: e2_knowledge_check

> 傷口在光芒中迅速癒合，只留下一道淡淡的痕跡。你感覺好多了。

<!-- ═══════════════════════════════════════════ -->
<!-- 知識檢定：活化冰錐的來歷 -->
<!-- ═══════════════════════════════════════════ -->

## 知識檢定成功 #e2_knowledge_pass
speaker: dm
next: e2_dragon_runs

> 你想起了什麼——活化冰錐是一種魔法生物，**冰巨魔有時會用它們來守護自己的領地**。如果這裡有活化冰錐守衛，那就意味著冰巨魔曾經到過這裡，甚至可能現在還在附近。
>
> 你把這個發現告訴了其他人。

sets_flag: icicle_knowledge

<!-- ═══════════════════════════════════════════ -->
<!-- 龍寶寶跑進洞穴 -->
<!-- ═══════════════════════════════════════════ -->

## 龍寶寶衝進洞穴 #e2_dragon_runs
speaker: dm

> 就在你們討論的時候，龍寶寶突然掙脫了你的視線，蹣跚著朝洞穴深處跑去。牠的小爪子在冰面上打滑，但牠義無反顧地往黑暗中鑽。
>
> 「等等——！」科爾隊長伸手想抓住牠，但已經來不及了。

sets_flag: encounter2_complete

choices:
- **「快追！不能讓牠一個人進去！」** #choice_e2_chase → e2_prepare_enter
- **「洞穴裡可能很危險……但我們不能丟下牠。」** #choice_e2_cautious → e2_prepare_enter
