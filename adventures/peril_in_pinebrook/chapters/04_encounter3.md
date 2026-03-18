---
chapter: 4
title: 危險的巢穴
---

<!-- ═══════════════════════════════════════════ -->
<!-- 進入洞穴：氛圍描述 + 壁畫 -->
<!-- ═══════════════════════════════════════════ -->

## 進入洞穴 #encounter3_enter_cave
trigger: enter_node dragon_cave
condition: has:chapter_03_complete
once: true

> 你們點燃——不，還不行。洞穴的入口被從洞口射進來的陽光照亮，但深處則一片黑暗。
>
> 牆上的一些粗糙素描引起了你們的注意——畫中描繪著像是巨魔的生物在跳舞和工作。這些壁畫看上去粗獷而原始。

- set_flag: encounter3_started
- tutorial: 和科爾隊長 **talk**（交談）來調查這些壁畫。

<!-- ═══════════════════════════════════════════ -->
<!-- 洞穴探索完成：揭示通往冰壁的路 -->
<!-- ═══════════════════════════════════════════ -->

## 探索完成 #e3_cave_explored_event
trigger: flag_set e3_cave_explored
once: true

> 火把的光芒照亮了前方蜿蜒向上的隧道。冰冷的空氣從隧道深處湧來。

- reveal_edge: cave_to_climb

<!-- ═══════════════════════════════════════════ -->
<!-- 挑戰 1：冰壁攀爬 -->
<!-- ═══════════════════════════════════════════ -->

## 進入冰壁 #e3_enter_climb
trigger: enter_node ice_climbing_wall
condition: has:e3_cave_explored
once: true

> 這條寒冷結霜的隧道越走越窄，最後在一面巨大的冰壁前戛然而止。垂直的岩壁覆蓋著一層寒冰，足足有五十呎高。通道在牆壁頂端繼續向前。

- tutorial: 和科爾隊長 **talk**（交談）來商量怎麼爬上去。

## 攀爬完成 #e3_climb_done
trigger: flag_set e3_wall_climbed
once: true

> 通道在冰壁頂端繼續向上延伸。空氣越來越冷。

- reveal_edge: climb_to_mirror

<!-- ═══════════════════════════════════════════ -->
<!-- 挑戰 2：魔力冰鏡 -->
<!-- ═══════════════════════════════════════════ -->

## 進入冰鏡 #e3_enter_mirror
trigger: enter_node magic_ice_mirror
condition: has:e3_wall_climbed
once: true

> 蜿蜒向上傾斜的通道突然被一層薄薄堅冰阻斷了。透過冰面，你可以看到通道在另一頭繼續向前。

- tutorial: 和科爾隊長 **talk**（交談）來面對這面冰牆。

## 冰鏡通過 #e3_mirror_done
trigger: flag_set e3_mirror_passed
once: true

> 冰鏡已經消失，通道繼續向上延伸。

- reveal_edge: mirror_to_slides

<!-- ═══════════════════════════════════════════ -->
<!-- 挑戰 3：冰道尋路 -->
<!-- ═══════════════════════════════════════════ -->

## 進入冰道 #e3_enter_slides
trigger: enter_node ice_slides
condition: has:e3_mirror_passed
once: true

> 你們來到了冰層峭壁的頂端。下方是山中的巨大洞穴，幾條石頭和冰塊組成的滑道在眼前鋪展。這些滑道陡峭、光滑，糾纏交叉成迷宮一般。

- tutorial: 和科爾隊長 **talk**（交談）來決定怎麼下去。

## 冰道完成 #e3_slides_done_event
trigger: flag_set e3_slides_done
once: true

- reveal_edge: slides_to_hatching

<!-- ═══════════════════════════════════════════ -->
<!-- 到達孵化洞 -->
<!-- ═══════════════════════════════════════════ -->

## 到達孵化洞 #e3_reach_hatching
trigger: enter_node hatching_cave
condition: has:e3_slides_done
once: true

> 你們走完最後一小段路，踏入了一個巨大的圓形洞室。穹頂高達十幾公尺，地面上散落著大量碎蛋殼和閃亮的小物品。
>
> 沉重而緩慢的呼吸聲在洞穴中迴盪——像海浪的潮汐。
>
> 龍寶寶掙脫你的視線，興奮地蹣跚著朝洞穴深處跑去。

- set_flag: e3_reached_hatching
- set_flag: chapter_04_complete

<!-- 接下來：遭遇 4 — 龍蛋與灼目之銀 -->
