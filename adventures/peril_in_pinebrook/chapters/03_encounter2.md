---
chapter: 3
title: 活化冰錐
---

<!-- ═══════════════════════════════════════════ -->
<!-- 抵達山腳：旅途敘事 + 觸發遭遇 2 -->
<!-- ═══════════════════════════════════════════ -->

## 抵達山腳 #encounter2_arrival
trigger: enter_node mountain_approach
condition: has:chapter_02_complete
once: true

> 你們沿著林間小路繼續前行。周圍的樹林異常安靜——沒有鳥叫，沒有蟲鳴，連風聲都像是被什麼東西吞噬了。龍寶寶反倒越來越興奮，小爪子不停地抓著你的褲腿。
>
> 通往山腳的路出奇地順利，沒有任何林中生物打擾你們。科爾隊長不時警覺地回頭張望，但什麼也沒有發現。
>
> 終於，樹木漸稀，你們看到前方不遠處有個寬敞的洞穴。世界之脊山的岩壁巍然聳立，積雪覆蓋的山頂在陽光下閃著冷光。
>
> 如果這座山裡真的有一條龍築巢，那麼這個洞穴可能就是入口。

- set_flag: encounter2_started
- tutorial: 和科爾隊長 **talk**（交談）來繼續。

<!-- ═══════════════════════════════════════════ -->
<!-- 戰鬥勝利後：揭示洞穴入口 -->
<!-- ═══════════════════════════════════════════ -->

## 冰錐擊敗 #encounter2_victory
trigger: flag_set icicles_defeated
once: true

- narrate: 戰鬥的塵埃落定。洞穴入口重歸寂靜。

## 遭遇 2 完成 #encounter2_done
trigger: flag_set encounter2_complete
once: true

> 龍寶寶消失在洞穴的黑暗中。你們必須跟上去。

- reveal_edge: path_to_cave
- set_flag: chapter_03_complete

<!-- 接下來：遭遇 3 — 危險的巢穴 -->
