---
chapter: 5
title: 龍蛋與灼目之銀
---

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 4：竊蛋獸戰鬥 -->
<!-- ═══════════════════════════════════════════ -->

## 遭遇開始 #encounter4_start
trigger: flag_set chapter_04_complete
once: true

- tutorial: 和科爾隊長 **talk**（交談）來應對孵化洞裡的威脅。

## 竊蛋獸擊敗 #encounter4_victory
trigger: flag_set e4_battle_won
once: true

> 竊蛋獸被擊退了。銀色的巨蛋完好無損——你們成功保護了龍巢。

<!-- ═══════════════════════════════════════════ -->
<!-- 勞恩登場 -->
<!-- ═══════════════════════════════════════════ -->

## 勞恩出現 #encounter4_rorn_appears
trigger: flag_set e4_rorn_appeared
once: true

> 一條碩大無比的銀龍降落在你們面前。整個洞穴都在她的重量下震動。

- tutorial: 和銀龍 **talk**（交談）來回應她的質問。這條龍無比強大——攻擊她不是明智之舉。

## 勞恩緩和 #encounter4_rorn_calmed
trigger: flag_set rorn_calmed
once: true

> 洞穴中的寒氣消散了。銀龍的目光變得溫柔。龍寶寶歡快地在母親巨大的爪子間蹣跚跑動。

<!-- ═══════════════════════════════════════════ -->
<!-- 尾聲 -->
<!-- ═══════════════════════════════════════════ -->

## 蛋孵化 #encounter4_eggs_hatch
trigger: flag_set epilogue_eggs_hatched
once: true

> 三條小龍擠在母親身邊，爭先恐後地吃著東西。勞恩的目光在幼龍和你們之間來回移動，眼中滿是感激。

- tutorial: 繼續和勞恩 **talk**（交談）。

## 冒險完成 #encounter4_complete
trigger: flag_set adventure_complete
once: true

- set_flag: chapter_05_complete
