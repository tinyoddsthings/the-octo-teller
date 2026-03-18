---
id: evendorn
name: 埃文多恩
---

## 背景
description: 溫和的半精靈牧師，手持刻有新月紋路的聖徽。說話輕聲細語，目光溫暖而堅定。
location: forest_trail_start
personality: 沉穩、虔誠、善良。話不多但每句都經過深思熟慮。
role: companion

## 常態對話 #evendorn_idle

> 「月之女神保佑我們。」

## 巡邏途中 #evendorn_patrol
condition: has:patrol_departed

> 埃文多恩一邊走一邊低聲祈禱，手指輕撫聖徽。
> 「今天的風不太對……帶著一股寒意。希望是我多慮了。」

## 埃文多恩自介 #companion_evendorn_intro
next: companion_gallantine_intro

> 埃文多恩微微頷首，手中握著一枚刻有新月紋路的聖徽：「我是埃文多恩，侍奉月之女神。治療術是我的本職——希望今天用不上。」

## 擔心回應（埃文多恩） #troll_worried_evendorn
next: troll_worried_gallantine

> 「如果真的是冰巨魔回來了，光靠祈禱恐怕不夠……我們得做好萬全準備。」

## 銀龍回應（埃文多恩） #troll_confident_evendorn
next: troll_confident_shalefire

> 埃文多恩搖搖頭：「傳說之所以流傳，往往有其道理。不過……的確沒有人親眼見過。」

## 懷疑回應（埃文多恩） #troll_doubt_evendorn

> 埃文多恩沉思片刻：「不管真假，保持警覺總沒錯。」

choices:
- **「那之前的冰巨魔是怎麼被趕走的？」** #choice_ask_history → troll_history
- **「好吧，我會留意的。」** #choice_end_doubt → kole_depart
  sets_flag: troll_discussed

## 好奇回應 #troll_curious_response
next: troll_curious_shalefire

> 埃文多恩溫和地解釋：「冰巨魔是一種巨大的人形生物，皮膚像冰塊一樣堅硬。它們在寒冷的地方出沒，力量驚人。」

## 銀龍之謎 #troll_dragon_mystery
next: troll_dragon_gallantine

> 埃文多恩若有所思：「有些龍喜歡以不同的姿態行走於世間。也許牠一直在附近，只是我們認不出來。」

## 冰巨魔歷史（埃文多恩） #troll_history_evendorn

> 埃文多恩低聲說：「願那些犧牲的人安息。」

choices:
- **「不會再讓那種事發生的。」** #choice_end_history → kole_depart
  sets_flag: troll_discussed

## 冰巨魔被驅趕（埃文多恩） #troll_driven_evendorn
next: troll_driven_shalefire

> 「如果傳說中的銀龍和冰巨魔的出沒有關……事情可能比我們想的更複雜。」

## 埃文多恩攻擊 #e2_npc_evendorn
next: e2_npc_kole

> 埃文多恩舉起聖徽，一道光芒擊中第三隻冰錐。冰錐的身體出現裂痕，但還沒有倒下。
> 「它還在動——小心！」

## 治療提示 #e2_heal_prompt

> 埃文多恩走過來，看了看你手臂上的傷口，皺了皺眉。
> 「讓我來。」他握住聖徽，低聲祈禱。溫暖的光芒從他的手中流淌出來，覆蓋在你的傷口上。

- tutorial: 埃文多恩使用了 **療傷術（Cure Wounds）**，這是一個消耗 1 個法術欄位的治療法術。岩炎也有一次性的自我治療能力（戰士的「復甦力」）。在這場冒險中，治療手段有限——小心管理你的生命值。

next: e2_healed

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 3：危險的巢穴 -->
<!-- ═══════════════════════════════════════════ -->

## 洞穴祈禱 #e3_evendorn_cave
condition: has:encounter3_started

> 埃文多恩握緊聖徽，低聲喃喃：「月之女神保佑……這裡的空氣不太對。有一股……古老的氣息。」

## 辨認巴哈姆特 #e3_evendorn_bahamut
condition: has:e3_bahamut_identified

> 埃文多恩單膝跪地，手中的聖徽散發出微弱的光芒。
> 「巴哈姆特……金屬龍之神，正義與慈悲的守護者。」
> 他的聲音帶著敬畏。
> 「能見到祂的顯現，即使只是影像……這是無上的榮幸。」

## 祝福感恩 #e3_evendorn_blessing
condition: has:e3_blessed

> 埃文多恩閉上眼睛，雙手合十：「感謝巴哈姆特的恩賜。這份祝福會保護我們度過接下來的考驗。」
> 他睜開眼，看了看自己的手——傷口已經完全癒合了。

## 攀爬關心 #e3_evendorn_climb
condition: all:has:e3_cave_explored,not:e3_wall_climbed

> 埃文多恩仰望冰壁，抿了抿嘴：「如果有人摔下來……我還有治療法術。但請大家小心。」

## 冰道祈禱 #e3_evendorn_slides
condition: all:has:e3_mirror_passed,not:e3_slides_done

> 埃文多恩看著下方的冰道迷宮，搖了搖頭。
> 「月之女神啊……」
> 他握緊聖徽，低聲祈禱了幾句，然後深吸一口氣。
> 「準備好了。」

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 4：龍蛋與灼目之銀 -->
<!-- ═══════════════════════════════════════════ -->

## 埃文多恩保護蛋 #e4_npc_evendorn
next: e4_npc_kole_attack

> 埃文多恩迅速移動到龍蛋旁邊，用身體擋在蛋和竊蛋獸之間。他舉起聖徽，一道光芒擊中了衝來的生物。
> 「我來保護龍蛋——你們去解決它們！」

## 科爾攻擊 #e4_npc_kole_attack
next: e4_snatcher_counterattack

> 科爾隊長和加侖丁左右夾擊，劍與刀同時落下。竊蛋獸慘叫一聲，掙扎著想逃，但被逼入了死角。
> 科爾隊長回頭看了你一眼：「剩一隻——輪到你了！」

## 埃文多恩治療 #e4_evendorn_heal
condition: has:e4_battle_won

> 埃文多恩走到你身邊，查看你的傷勢。
> 「讓我看看……」他握住聖徽，溫暖的光芒再次流淌出來。
> 「還好，不算嚴重。」

## 埃文多恩敬畏 #e4_evendorn_rorn
condition: all:has:e4_rorn_appeared,not:rorn_calmed

> 埃文多恩再次單膝跪地，聖徽散發出柔和的光芒。
> 「灼目之銀……」他低聲說道，聲音帶著深深的敬畏。
> 「月之女神保佑，我們有幸見證了傳說。」

## 埃文多恩尾聲 #e4_evendorn_epilogue
condition: has:rorn_calmed

> 埃文多恩溫和地看著三條幼龍在母親身邊嬉戲。
> 「新生命的誕生……這是我見過最美的景象。」
> 他轉向你，微微一笑。
> 「今天的一切都值得了。」
