---
chapter: 2
title: 一條並不那麼可怕的龍
---

<!-- ═══════════════════════════════════════════ -->
<!-- 進入密林深處：觸發遭遇 1 -->
<!-- ═══════════════════════════════════════════ -->

## 深入密林 #encounter1_enter
trigger: enter_node deep_forest
condition: has:chapter_01_complete
once: true

> 你們在林中小徑穿行了約十五分鐘。樹木越來越密，陽光幾乎被完全遮擋。四周安靜得不尋常——連鳥叫聲都消失了。
>
> 科爾隊長突然停下腳步。

- set_flag: encounter1_started
- tutorial: 和科爾隊長 **talk**（交談）來回應她的問題。

<!-- ═══════════════════════════════════════════ -->
<!-- 獲得龍語書頁 -->
<!-- ═══════════════════════════════════════════ -->

## 獲得龍語書頁 #get_dragon_page
trigger: flag_set has_dragon_page
once: true

- add_item: dragon_language_page
- narrate: 你獲得了「龍語翻譯書頁」。可以在之後的冒險中用來和龍類溝通。

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 1 完成：揭示前往山腳的路 -->
<!-- ═══════════════════════════════════════════ -->

## 遭遇完成 #encounter1_done
trigger: flag_set encounter1_complete
once: true

> 銀龍寶寶歡快地跟在你身後，偶爾用小鼻子蹭你的腳踝。遠處的山峰在夕陽下泛著金光。

- reveal_edge: trail_to_mountain
- set_flag: chapter_02_complete

<!-- 接下來：遭遇 2 — 活化冰錐 -->
