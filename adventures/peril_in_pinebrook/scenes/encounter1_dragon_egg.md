---
id: encounter1_dragon_egg
name: 遭遇 1——龍蛋發現（DM 旁白）
---

<!-- 遭遇 1 的 DM 旁白段，被 emmajeen_kole 的 next 引用進入 -->

## 玩家察覺成功 #encounter1_player_noticed
speaker: dm
next: encounter1_dragon_appears

> 你側耳傾聽——從小路邊荊棘叢生的灌木叢中，傳來一陣窸窣的騷動。有什麼東西在裡面。

sets_flag: perception_done

## 龍寶寶現身 #encounter1_dragon_appears
speaker: dm
next: encounter1_dragon_reaction

> 小路邊的灌木叢沙沙作響，一頭小狗大小的生物從荊棘和樹葉中蹣跚爬出。
>
> 乍一看，這隻生物像一隻金屬製成的巨大蜥蜴。但當你們仔細打量，才認出這是一條小龍——長著藍灰色的鱗片，吐著長長的、細尖的舌頭。
>
> 小龍一邊爬向你們，一邊無力地試圖剝下臉上和頭頂的銀色蛋殼碎片。牠發出嘶嘶的嗚嚶聲。

## 靠近龍寶寶 #encounter1_approach
speaker: dm
next: encounter1_identify_prompt

> 你小心翼翼地靠近。小龍歪著頭看著你，嗚嚶了一聲，然後用小小的前爪抓住你的靴子，試圖往上爬。牠的鱗片摸起來微涼，像打磨過的銀幣。

## 觀察龍寶寶 #encounter1_observe
speaker: dm
next: encounter1_identify_prompt

> 你退後半步，仔細觀察。小龍似乎對你們沒有敵意——牠蹣跚地在地上爬行，一邊嗚嚶一邊用頭蹭地面，想把頭頂殘留的蛋殼碎片磨掉。牠看起來……很餓。

## 玩家辨識成功 #encounter1_identified
speaker: dm
next: encounter1_kole_book

> 你仔細觀察那藍灰色的鱗片——不，那是銀色的，只是沾了泥土和蛋液。這是一隻剛從蛋裡孵出來的銀龍寶寶！銀龍通常吃肉和堅果等食物，而且牠們對人類相當友善。

## 語言說明 #encounter1_language_explain
speaker: dm

> 在這個世界裡，大多數智慧種族都使用「通用語」交流。但有些種族有自己獨特的語言——精靈語、矮人語、獸人語、龍語等等。在未來創建角色時，你可以選擇角色額外會說的語言。不過在這場冒險裡，你只需要通用語和這張龍語翻譯書頁就夠了。

choices:
- **「了解了。那現在這隻小龍怎麼辦？」** #choice_what_now → encounter1_kole_leaves
- **「龍語聽起來很酷，我想學。」** #choice_want_dragon_lang → encounter1_kole_leaves_eager

<!-- ═══════════════════════════════════════════ -->
<!-- 餵食階段 -->
<!-- ═══════════════════════════════════════════ -->

## 餵食提示 #encounter1_feeding_prompt
speaker: dm
condition: has:kole_left

> 小龍用水汪汪的眼睛望著你，肚子發出咕嚕咕嚕的聲音。牠顯然餓壞了。

choices:
- **「用我的口糧餵牠。」** #choice_feed_ration → encounter1_fed_ration
  sets_flag: dragon_fed
- **「我去附近找找有沒有能吃的東西。」** #choice_feed_forage → encounter1_forage_check

## 覓食檢定 #encounter1_forage_check
speaker: dm

> 你在附近的灌木叢間搜索，看看有沒有小龍能吃的東西……

skill_check:
  skill: Survival
  dc: 10
  pass: encounter1_fed_forage
  fail: encounter1_forage_failed

## 覓食失敗 #encounter1_forage_failed
speaker: dm
next: encounter1_dragon_nytha

> 你翻找了一圈，但這片林子裡的漿果不是有毒就是還沒成熟。看來還是得用口糧了。

sets_flag: dragon_fed

## 用口糧餵食 #encounter1_fed_ration
speaker: dm
next: encounter1_dragon_nytha

> 你從背包裡拿出一份口糧。小龍聞了聞，然後狼吞虎嚥地把乾肉條和硬餅吃了個精光。牠滿足地打了個小嗝，鼻孔裡噴出一縷淡淡的白霧。

## 找到漿果餵食 #encounter1_fed_forage
speaker: dm
next: encounter1_dragon_nytha

> 你在附近的灌木叢裡找到了一把深紫色的漿果和幾顆松子。小龍急不可耐地湊過來，用小舌頭一顆一顆舔走漿果，然後用爪子靈巧地剝開松子殼。吃完後牠滿足地打了個小嗝，鼻孔裡噴出一縷淡淡的白霧。

## 龍寶寶說話 #encounter1_dragon_nytha
speaker: dm
next: encounter1_dragon_follows

> 小龍吃飽後精神明顯好了許多。牠抖了抖身上殘留的蛋殼碎片，然後抬起頭看著你，說出了一個詞：
>
> **「Nytha。」**
>
> 你還不知道這個詞的意思。但小龍說這話時，尾巴歡快地搖擺著。

## 龍寶寶跟隨 #encounter1_dragon_follows
speaker: dm

> 小龍振作起來，蹣跚地跟在你身後。當你停下來時，牠就爬上你的靴子；當你走動時，牠就小跑著追上。牠似乎特別喜歡被摸肚皮——每次你伸手過去，牠就翻過身露出銀白色的肚子，發出滿足的呼嚕聲。
>
> 透過樹林，你可以看到科爾隊長指引你們前去的那座山。

sets_flag: dragon_following
sets_flag: encounter1_complete
