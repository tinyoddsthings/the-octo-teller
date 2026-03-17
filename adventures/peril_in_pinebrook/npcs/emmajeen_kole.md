---
id: emmajeen_kole
name: 艾瑪金·科爾
---

## 背景
description: 松溪村巡邏隊隊長。短髮、目光銳利，腰間佩劍。雖然語氣帶著幾分緊張，但每個動作都透露出豐富的巡邏經驗。
location: forest_trail_start
personality: 警覺、負責。閒聊時語氣輕鬆，但眼神從不離開四周。對新隊員嚴格但不苛刻。
role: quest_giver

<!-- ═══════════════════════════════════════════ -->
<!-- 開場對話鏈：自我介紹 → 創角環節 → 冰巨魔討論 → 出發 -->
<!-- ═══════════════════════════════════════════ -->

## 初次見面 #kole_intro
map: forest_patrol
condition: not:intro_started

> 科爾隊長緊張兮兮地瞥了一眼林間小路，然後向你們點頭示意。
> 「我以前沒跟你們任何一個人巡邏過。簡單介紹一下自己吧。」

sets_flag: intro_started

## 詢問名字 #kole_ask_name

> 科爾隊長滿意地點了點頭，然後轉向你，挑了挑眉。
> 「好，輪到你了——你叫什麼名字？」

sets_flag: companions_introduced

<!-- 此處由引擎觸發 CharacterBuilder 角色命名 -->
<!-- 玩家輸入名字後設定 player_named flag -->

## 詢問專長 #kole_ask_specialty
condition: all:has:companions_introduced,has:player_named,not:specialty_chosen

> 「不錯，記住了。」科爾隊長點點頭。
> 「那你平時擅長什麼？巡邏隊裡各有各的長處——像岩炎是近戰主力，埃文多恩負責支援。你呢？」

choices:
- **「我擅長近戰搏鬥，衝在最前面。」** #choice_melee → kole_ack_specialty
  sets_flag: specialty_melee
- **「我擅長遠程射擊，在後方掩護。」** #choice_ranged → kole_ack_specialty
  sets_flag: specialty_ranged
- **「我會使用法術。」** #choice_magic → kole_ack_specialty
  sets_flag: specialty_magic
- **「我比較擅長偵查和潛行。」** #choice_stealth → kole_ack_specialty
  sets_flag: specialty_stealth

## 回應專長 #kole_ack_specialty
condition: any:has:specialty_melee,has:specialty_ranged,has:specialty_magic,has:specialty_stealth

> 科爾隊長若有所思地點頭：「嗯，隊裡正好需要。」

sets_flag: specialty_chosen

## 詢問裝備 #kole_ask_equipment
condition: all:has:specialty_chosen,not:equipment_chosen

> 科爾隊長掃了你一眼，視線停在你身上。
> 「那今天帶了什麼東西防身？讓我看看。」

choices:
- **「我帶了一把劍和盾牌。」** #choice_sword_shield → kole_ack_equipment
  sets_flag: equip_sword_shield
- **「我帶了弓和一壺箭。」** #choice_bow → kole_ack_equipment
  sets_flag: equip_bow
- **「我帶了一根法杖。」** #choice_staff → kole_ack_equipment
  sets_flag: equip_staff
- **「……呃，我什麼都沒帶。」** #choice_no_weapon → kole_give_weapon

## 科爾分配武器 #kole_give_weapon
condition: has:equip_none

> 科爾隊長翻了個白眼，嘆了口氣，從腰間解下一把短劍遞過來。
> 「……拿著。別讓我後悔帶你出來。」

sets_flag: equip_short_sword

## 回應裝備 #kole_ack_equipment

> 「好。」科爾隊長簡短地應了一聲，目光已經移向遠處的林子。

sets_flag: equipment_chosen

<!-- ═══════════════════════════════════════════ -->
<!-- 冰巨魔討論：多輪對話，NPC 參與 -->
<!-- ═══════════════════════════════════════════ -->

## 冰巨魔話題 #kole_ask_troll
condition: all:has:equipment_chosen,not:troll_discussed

> 科爾隊長壓低了聲音，表情變得嚴肅起來。
> 「說到正經的——你們也聽說了吧？昨天有人在林子裡發現了帶霜的巨大足跡。」
> 她頓了頓。
> 「冰巨魔已經兩個多月沒出現了。你對這事怎麼看？」

choices:
- **「聽起來很危險，我們得多加小心。」** #choice_troll_worried → troll_worried_response
- **「不怕！不是說有銀龍保護這一帶嗎？」** #choice_troll_confident → troll_confident_response
- **「也許只是普通動物的足跡吧？」** #choice_troll_doubt → troll_doubt_response
- **「冰巨魔是什麼？我不太了解。」** #choice_troll_curious → troll_curious_response

## 擔心回應（科爾） #troll_worried_kole

> 科爾隊長皺著眉：「這正是我擔心的。」

choices:
- **「那我們今天巡邏要特別注意什麼？」** #choice_ask_precaution → troll_precaution
- **「走著瞧吧，遇到再說。」** #choice_end_worried → kole_depart
  sets_flag: troll_discussed

## 懷疑回應 #troll_doubt_response
next: troll_doubt_shalefire

> 科爾隊長搖了搖頭：「我親眼看過那些足跡——足足有這麼大。」她張開雙臂比了個誇張的尺寸。

## 好奇回應（科爾） #troll_curious_kole

> 科爾隊長正色道：「牠們通常不會靠近村莊，但如果有什麼東西把牠們從山裡趕出來了，那就是大問題。」

choices:
- **「什麼東西會把冰巨魔從山裡趕出來？」** #choice_troll_driven → troll_driven_out
- **「了解了，我會小心的。」** #choice_end_curious → kole_depart
  sets_flag: troll_discussed

## 巡邏注意事項 #troll_precaution
next: troll_precaution_shalefire

> 科爾隊長豎起手指一一數道：「第一，注意地面——有沒有不尋常的足跡或霜痕。第二，留意氣溫變化——冰巨魔經過的地方，溫度會驟降。第三……」
> 她拍了拍腰間的劍。
> 「遇到了別逞強。活著回去報告比當英雄重要。」

## 銀龍之謎（科爾） #troll_dragon_kole

> 科爾隊長拍了拍手：「好了，傳說歸傳說。」

choices:
- **「或許今天巡邏就能找到線索。」** #choice_end_dragon → kole_depart
  sets_flag: troll_discussed

## 冰巨魔歷史 #troll_history
next: troll_history_shalefire

> 科爾隊長回憶道：「那是好幾年前的事了。一群冰巨魔從世界之脊山的深處下來，襲擊了幾個外圍營地。」

## 冰巨魔被驅趕 #troll_driven_out
next: troll_driven_gallantine

> 科爾隊長沉吟片刻：「老實說……我不知道。牠們有自己的地盤，通常不會離開。除非有更強大的東西入侵了牠們的領地。」

<!-- ═══════════════════════════════════════════ -->
<!-- 結束對話，出發巡邏 -->
<!-- ═══════════════════════════════════════════ -->

## 出發 #kole_depart
condition: has:troll_discussed

> 科爾隊長拍了拍手，神情一振。
> 「好了！我們還要巡邏呢，趕快動身吧。我們為必要的戰鬥做好準備了！」

sets_flag: patrol_departed

## 常態對話 #kole_idle
condition: all:has:patrol_departed,not:encounter1_started

> 「別掉隊。」

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 1：一條並不那麼可怕的龍 -->
<!-- ═══════════════════════════════════════════ -->

## 你們聽到了什麼嗎 #kole_perception_prompt
condition: all:has:encounter1_started,not:perception_done

> 科爾隊長安靜地舉起一隻手，示意大家停下。
> 「你們聽到了什麼嗎？」

- tutorial: 這是一次 **察覺檢定**（Perception Check）。擲一個 d20（二十面骰——之後會用 dX 表示 X 面骰），加上角色卡「技能」欄中察覺旁的數字。通過的難度等級為 **DC 10**（Difficulty Class 10），即結果 ≥ 10 就算成功。

skill_check:
  skill: Perception
  dc: 10
  pass: encounter1_player_noticed
  fail: encounter1_kole_noticed
  assists:
  - 導引術 #guidance | evendorn | 1d4 | concentration

## 科爾察覺 #encounter1_kole_noticed

> 科爾隊長皺了皺眉，食指指向小路右側的一叢荊棘。
> 「那邊——灌木叢裡有東西在動。」

sets_flag: perception_done
next: encounter1_dragon_appears

## 龍寶寶反應 #encounter1_dragon_reaction

> 科爾隊長疑惑地看著這一切，手不自覺地放在劍柄上，但沒有拔劍。
> 「這是……什麼東西？」

choices:
- **「好可愛！我想靠近看看。」** #choice_approach → encounter1_approach
  sets_flag: player_approached_dragon
- **「小心，可能有危險。先觀察一下。」** #choice_observe → encounter1_observe
  sets_flag: player_observed_dragon
- **「這該不會是一條龍吧？」** #choice_guess_dragon → encounter1_guess_dragon
  sets_flag: player_guessed_dragon
- **「我們應該殺了牠以防萬一。」** #choice_attack_dragon → encounter1_kole_refuses

## 科爾拒絕傷害 #encounter1_kole_refuses
next: encounter1_dragon_reaction

> 科爾隊長迅速擋在你和小龍之間，神情嚴厲。
> 「住手！我們還不知道這是什麼。巡邏隊的規矩——不明生物先觀察，不主動攻擊。」
> 她的語氣不容置疑。

<!-- ═══════════════════════════════════════════ -->
<!-- 辨識階段：知識檢定 -->
<!-- ═══════════════════════════════════════════ -->

## 辨識提示 #encounter1_identify_prompt

> 科爾隊長蹲下來，若有所思地看著小龍。
> 「有人知道這到底是什麼嗎？看起來像……某種龍類？」

- tutorial: 你可以嘗試用技能來辨識這隻生物。岩炎可以用 **馴獸（Animal Handling）**，加侖丁可以用 **自然（Nature）**。DC 10。

skill_check:
  skill: Nature
  dc: 10
  pass: encounter1_identified
  fail: encounter1_kole_identifies

## 科爾辨識 #encounter1_kole_identifies
next: encounter1_kole_book

> 科爾隊長端詳了半天，突然眼睛一亮。
> 「等一下——我在書上看過這個。」

<!-- ═══════════════════════════════════════════ -->
<!-- 科爾的書 + 龍語書頁 -->
<!-- ═══════════════════════════════════════════ -->

## 科爾翻書 #encounter1_kole_book
next: encounter1_kole_book_info

> 科爾隊長從背包裡翻出一本書：《完全基本龍類指南 The Practically Complete Guide to Dragons》。她快速翻到書的中間，用手指比對著插圖和眼前的小龍。

## 科爾確認銀龍 #encounter1_kole_book_info
next: encounter1_kole_gives_page

> 「毫無疑問！這是一條新生的銀龍。牠媽媽的巢穴肯定就在林子對面最近的山上——和傳說中一樣。」
> 她抬頭看向遠方的山峰。
> 「我們必須趕快把這個寶寶送回牠媽媽身邊。我很好奇，這個寶寶是怎麼離家這麼遠的？」

## 科爾給書頁 #encounter1_kole_gives_page
next: encounter1_language_explain

> 科爾隊長撕下一頁紙，遞給你。
> 「拿著。這個可能會有用。根據書上所寫，銀龍們都很平和，而且通常都喜歡人類。」
> 科爾隊長交給你的書頁上記載了龍語和通用語的對照翻譯——龍語是龍類使用的語言，而通用語是你們熟知的語言。

sets_flag: has_dragon_page

## 科爾離開（關心） #encounter1_kole_leaves
next: encounter1_feeding_prompt

> 科爾隊長站起身，拍了拍膝蓋上的泥土。
> 「我得回去向村裡報告這件事。你們先照顧好這條小龍——餵牠點東西吃，別讓牠跑掉。等我回來，我們就出發去山上找牠媽媽。」
> 她快步沿著小路消失在林間。

sets_flag: kole_left

## 科爾離開（熱情） #encounter1_kole_leaves_eager
next: encounter1_feeding_prompt

> 科爾隊長忍不住笑了笑：「心不急，先把小龍照顧好再說。」
> 她站起身來。
> 「我得回去向村裡報告這件事。你們先照顧好牠——餵牠點東西吃。等我回來，我們就出發去山上找牠媽媽。」
> 她快步沿著小路消失在林間。

sets_flag: kole_left

## 遭遇後常態 #kole_post_encounter
condition: all:has:encounter1_complete,not:encounter2_started

> 「小龍還好嗎？別讓牠掉隊了。」

<!-- ═══════════════════════════════════════════ -->
<!-- 遭遇 2：活化冰錐 -->
<!-- ═══════════════════════════════════════════ -->

## 洞穴入口 #e2_cave_approach
condition: all:has:encounter2_started,not:e2_combat_started
next: e2_dragon_sniff

> 科爾隊長指著前方：「看——那個洞穴。如果這座山裡真的有龍築巢，那就是入口了。」

## 科爾攻擊 #e2_npc_kole
next: e2_player_turn

> 科爾隊長的劍精準地切下那隻裂了的冰錐的頭部。冰錐轟然倒地。
> 「三個了。還有兩個——」她朝你看來。「輪到你了！」

- tutorial: 三隻冰錐已被隊友擊敗，剩下 **兩隻活化冰錐**。現在輪到你行動！

## 受傷反應 #e2_player_hit_reaction

> 科爾隊長大喊：「別慌！它只剩最後一口氣了！」

choices:
- **「再來一次！反擊！」** #choice_e2_counter → e2_final_blow
- **「隊友幫幫忙！」** #choice_e2_help → e2_ally_finish

## 搜索提示 #e2_search_prompt

> 科爾隊長點點頭：「做得好。現在——搜搜看周圍有沒有什麼有用的東西。有些怪物會守著寶藏。」

- tutorial: 擊敗怪物後搜索周圍是個好習慣。有些寶藏藏在附近，有些可以直接找到。

choices:
- **「搜索洞穴入口附近。」** #choice_e2_search → e2_found_pack

## 知識檢定提示 #e2_knowledge_check

> 科爾隊長踢了踢地上的冰渣，若有所思。
> 「這些冰做的東西……不像是自然形成的。有人知道這到底是什麼嗎？」

- tutorial: 嘗試一次知識檢定——**奧秘（Arcana）** 或 **歷史（History）**，DC 10。

skill_check:
  skill: Arcana
  dc: 10
  pass: e2_knowledge_pass
  fail: e2_knowledge_fail
  assists:
  - 導引術 #guidance_e2 | evendorn | 1d4 | concentration

## 準備進入 #e2_prepare_enter

> 科爾隊長深吸一口氣，拔出劍。
> 「帶上火把。裡面很黑。」

- tutorial: 準備好後，前進進入洞穴。

sets_flag: ready_for_cave
