---
id: encounter3_dangerous_nest
name: 遭遇 3——危險的巢穴（DM 旁白）
---

<!-- ═══════════════════════════════════════════ -->
<!-- 洞穴入口：歷史/宗教檢定 -->
<!-- ═══════════════════════════════════════════ -->

## 洞穴壁畫檢定 #e3_history_check
speaker: dm

> 洞穴牆上的那些粗糙素描引起了你們的注意——畫中的巨大生物似乎在某種儀式中跳舞和勞作。這些畫是誰留下的？

- tutorial: 嘗試一次知識檢定——**歷史（History）** 或 **宗教（Religion）**，DC 10。埃文多恩擁有宗教技能加值，加侖丁擁有歷史技能加值。其他角色也可以嘗試，但不能加上任何加值。

skill_check:
  skill: History
  dc: 10
  pass: e3_history_pass
  fail: e3_history_fail

## 辨識成功 #e3_history_pass
speaker: dm
next: e3_torch_needed

> 你認出了這些壁畫——這是冰巨魔的原始藝術。冰巨魔曾經在這個洞穴中工作和生活。牠們可能把這裡當作了自己的據點。

sets_flag: e3_troll_cave_known

## 辨識失敗 #e3_history_fail
speaker: dm
next: e3_torch_needed

> 你無法辨認出這些壁畫的來歷。不過，龍寶寶進入洞穴後變得更加興奮，好像牠知道離家越來越近了。
>
> 在洞穴深處幾乎看不見的陰影中，一條通道向上延伸，成為了一條前往山體中心的隧道。

## 需要火把 #e3_torch_needed
speaker: dm

> 深處一片漆黑。如果不點亮火把，你們將什麼也看不到。

- tutorial: 使用先前在舊皮包裡找到的 **火把** 和 **打火石** 來照亮前路。

choices:
- **「點燃火把，繼續前進。」** #choice_e3_light_torch → e3_torch_lit

## 火把點燃 #e3_torch_lit
speaker: dm

> 打火石迸出火花，火把猛地亮了起來。搖曳的火光照亮了冰冷的石壁，前方的隧道蜿蜒向上。龍寶寶的鱗片在火光下閃爍著銀色的微光。

sets_flag: e3_cave_explored

<!-- ═══════════════════════════════════════════ -->
<!-- 挑戰 1：攀爬冰壁 -->
<!-- ═══════════════════════════════════════════ -->

## 冰壁描述 #e3_wall_description
speaker: dm
next: e3_climb_check

> 隧道在這裡戛然而止——面前是一面覆蓋著寒冰的垂直岩壁，足足有五十呎高。通道在上方繼續向前。你們必須爬上這面牆。
>
> 冰面濕滑，但岩壁上有一些可以抓握的凸起。寒氣從冰面透出，凍得指尖發麻。

## 攀爬檢定 #e3_climb_check
speaker: dm

> 準備好攀爬了嗎？

- tutorial: 進行一次 **運動（Athletics）** 或 **體操（Acrobatics）** 檢定，DC 10。如果你的裝備中有 **攀爬工具（Climber's Kit）**，這次檢定獲得 **優勢**（擲兩次 d20 取高）。失敗的角色會在爬到頂端前墜落，受到 **1d6** 點傷害。爬上頂端的角色可以降下 **繩索** 幫助其他人免檢定直接爬上。

skill_check:
  skill: Athletics
  dc: 10
  pass: e3_climb_pass
  fail: e3_climb_fail

## 攀爬成功 #e3_climb_pass
speaker: dm

> 你找到了合適的抓握點，手腳並用穩穩地向上攀爬。冰面在你的手指下嘎吱作響，但你每一步都踩得很穩。
>
> 終於，你翻上了頂端，通道在你面前繼續延伸。

sets_flag: e3_wall_climbed

## 攀爬失敗 #e3_climb_fail
speaker: dm

> 你的手指在冰面上打滑——腳下一空，整個人摔了下去！你在半空中拼命抓住了一塊凸起的岩石，減緩了衝擊，但依然重重地撞上了地面。
>
> **你受到了 1d6 點墜落傷害。**
>
> 揉了揉撞痛的地方，你再次嘗試——這一次更加小心，終於爬上了頂端。

sets_flag: e3_wall_climbed

<!-- ═══════════════════════════════════════════ -->
<!-- 挑戰 2：魔力冰鏡 -->
<!-- ═══════════════════════════════════════════ -->

## 冰鏡倒影 #e3_mirror_reflection
speaker: dm
next: e3_bahamut_appears

> 火把的光芒照到冰面上，突然間，冰面如同鏡子一樣反射出你們的身影——但那不是你們的模樣。
>
> 在這些倒影中，你和你的同伴都變成了銀龍，長著閃亮的鱗片和優雅的翅膀。而小龍寶寶的倒影，看起來卻像是一個長著銀色皮膚的人類幼童。

## 巴哈姆特現身 #e3_bahamut_appears
speaker: dm
next: e3_bahamut_identify

> 倒影消散，取而代之的是一具巨大的白金龍頭——牠從冰面中浮現，雙眼散發著溫暖的金色光芒。
>
> 白金龍頭開口說話。奇怪的是，你聽得懂牠在說什麼，即使牠說的不是你懂的語言。

## 辨認龍頭 #e3_bahamut_identify
speaker: dm

> 這是什麼神聖存在？

- tutorial: 嘗試一次 **奧秘（Arcana）**、**歷史（History）** 或 **宗教（Religion）** 檢定，DC 10。

skill_check:
  skill: Religion
  dc: 10
  pass: e3_bahamut_known
  fail: e3_bahamut_unknown

## 辨認成功 #e3_bahamut_known
speaker: dm
next: e3_bahamut_riddle

> 你認出了這個形象——這是 **巴哈姆特**，金屬龍之神，所有黃銅、青銅、赤銅、金龍和銀龍的守護者。牠是正義與慈悲的化身。

sets_flag: e3_bahamut_identified

## 辨認失敗 #e3_bahamut_unknown
speaker: dm
next: e3_bahamut_riddle

> 你不認得這個龍頭的身份，但從牠散發出的氣場來看，這無疑是一個極其古老而神聖的存在。

## 巴哈姆特的謎題 #e3_bahamut_riddle
speaker: dm

> 白金龍頭的聲音在隧道中迴盪：
>
> **「你們正在進行一項受祝福的任務，但你必須用正確的語言說出正確的字，才能進入我孩子的巢穴。」**
>
> **「哪兩個字能正確回答這個問題：你要護送什麼樣的生物回家？」**

choices:
- **「銀龍！」**（用通用語回答） #choice_e3_answer_common → e3_riddle_wrong_language
- **翻開龍語翻譯書頁尋找答案。** #choice_e3_use_page → e3_riddle_translate
- **嘗試用武器或火把破壞冰鏡。** #choice_e3_break_mirror → e3_mirror_break

## 語言不對 #e3_riddle_wrong_language
speaker: dm

> 巴哈姆特的表情沒有變化，但牠的聲音帶著一絲耐心：
>
> **「你說的意思是對的——但你用的不是正確的語言。」**

choices:
- **翻開龍語翻譯書頁尋找答案。** #choice_e3_use_page_2 → e3_riddle_translate
- **嘗試用武器或火把破壞冰鏡。** #choice_e3_break_mirror_2 → e3_mirror_break

## 翻譯答案 #e3_riddle_translate
speaker: dm

> 你翻開科爾隊長給你的龍語翻譯書頁，手指在對照表上快速掃過。
>
> 「銀」……「orn」。「龍」……「darastrix」。
>
> 你深吸一口氣，對著冰鏡上的白金龍頭大聲說出：

choices:
- **「Orn darastrix！」** #choice_e3_say_draconic → e3_mirror_blessing

## 巴哈姆特的祝福 #e3_mirror_blessing
speaker: dm

> 白金龍頭微微頷首，牠的眼中閃過一絲欣慰的光芒。
>
> 冰鏡迅速開始融化，化作一灘冰水潑到你們身上。但這並不寒冷——相反，當水從你們的皮膚、衣服和護甲上流下時，你們感覺到一陣酥麻，感覺十分美妙。
>
> 巴哈姆特祝福了這些水。

- tutorial: 巴哈姆特的祝福使所有角色的 **生命值恢復到最大值**。此外，每個角色在下一個挑戰中進行的 **第一次檢定獲得優勢**（擲兩次 d20 取高）。

sets_flag: e3_blessed
sets_flag: e3_mirror_passed

## 破壞冰鏡 #e3_mirror_break
speaker: dm

> 你揮動武器猛擊冰面——冰鏡炸裂開來！尖銳的冰片向四面八方飛濺，有些碎片割傷了你們。
>
> **你受到了 1d6 點傷害。**
>
> 冰鏡碎裂之處，通道確實出現了。但巴哈姆特的影像在最後一刻消散，你們沒有獲得任何祝福。

sets_flag: e3_mirror_passed

<!-- ═══════════════════════════════════════════ -->
<!-- 挑戰 3：冰道尋路 -->
<!-- ═══════════════════════════════════════════ -->

## 冰道描述 #e3_slides_description
speaker: dm
next: e3_cliff_collapse

> 你們站在冰層峭壁的頂端，俯瞰著山中的巨大洞穴。幾條石頭和冰塊組成的滑道在眼前鋪展開來——它們向下蜿蜒、相互交叉、首尾相連，形成了一個令人暈頭轉向的迷宮。
>
> 一些滑道的盡頭通往堅固的冰牆，而另一些則覆蓋著刀片般鋒利的冰錐。你們需要找出一條最合適的冰道下去。

## 峭壁崩塌 #e3_cliff_collapse
speaker: dm

> 突然，你們聽到一陣嘎吱聲。你們站立的峭壁開始崩塌！
>
> **如果現在還不跳向滑道的話，你們就要摔下去了！**

- tutorial: 每個角色都需要迅速跳向一條冰道。先進行一次 **調查（Investigation）** 或 **察覺（Perception）** 檢定，DC 10，嘗試在一瞬間辨認出最安全的路線。

skill_check:
  skill: Perception
  dc: 10
  pass: e3_slide_safe
  fail: e3_slide_danger

## 安全滑行 #e3_slide_safe
speaker: dm

> 你的眼睛在一瞬間掃過所有滑道——那條！最左邊的那條滑道表面最平滑，弧度也最舒緩！
>
> 你縱身一躍，雙腳踏上冰面，風在耳邊呼嘯而過。滑道帶著你高速滑行，左彎右繞，穿過冰冷的隧道，最終平穩地把你送到了洞穴底部。
>
> 雖然心臟還在狂跳，但你毫髮無傷。

sets_flag: e3_slides_done

## 危險滑行 #e3_slide_danger
speaker: dm

> 你來不及仔細觀察就跳了上去——滑道帶著你加速下墜！前方出現了一片刀片般鋒利的冰錐，你必須在最後一刻切換到旁邊的滑道！

- tutorial: 緊急閃避！進行一次 **體操（Acrobatics）** 或 **運動（Athletics）** 檢定，DC 15，嘗試跳到更安全的滑道。在角色卡中沒有這些技能的角色也可以嘗試，但不能加上任何調整值。

skill_check:
  skill: Acrobatics
  dc: 15
  pass: e3_slide_switch
  fail: e3_slide_hurt

## 切換成功 #e3_slide_switch
speaker: dm

> 在千鈞一髮之際，你猛地一個側翻，從這條滑道跳到了相鄰的另一條！冰錐從你身邊擦過，寒氣刺骨，但你成功避開了。
>
> 新的滑道帶著你平穩地滑向底部。驚險萬分，但你做到了。

sets_flag: e3_slides_done

## 滑行受傷 #e3_slide_hurt
speaker: dm

> 你試圖跳開，但冰面太滑了——你的身體在冰道上翻滾，鋒利的冰錐劃過你的手臂和腿。最後你砰地撞上了一面冰牆，滾進了另一條滑道，最終跌跌撞撞地到達了底部。
>
> **你受到了 1d6 點傷害。**

sets_flag: e3_slides_done

<!-- ═══════════════════════════════════════════ -->
<!-- 到達底部 -->
<!-- ═══════════════════════════════════════════ -->

## 到達底部 #e3_arrived_bottom
speaker: dm
condition: has:e3_slides_done

> 你們在洞穴底部重新集合。從這裡到孵化洞只剩一小段路了。
>
> 前方透出微弱的光芒，空氣中的寒意更加濃烈。沉重而緩慢的呼吸聲像海浪的潮汐一樣在洞穴中迴盪。
>
> 無論洞穴深處有什麼在等著你們——你們已經準備好面對了。
>
> 角色們準備好面對最終威脅了！

sets_flag: e3_ready_for_encounter4
