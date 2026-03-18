---
id: troll_discussion_dm
name: 冰巨魔討論——DM 旁白
---

<!-- 冰巨魔討論中的 DM 旁白橋接段，被 shalefire/gallantine 的 next 引用 -->

## 銀龍回應（科爾） #troll_confident_kole
speaker: dm

> 科爾隊長沒有表態，只是若有所思地看著遠方。

choices:
- **「如果銀龍真的存在，為什麼不出面？」** #choice_dragon_why → troll_dragon_mystery
- **「好吧，我們還是靠自己比較實際。」** #choice_end_confident → kole_depart
  sets_flag: troll_discussed

## 冰巨魔被驅趕（沉默） #troll_driven_dm
speaker: dm
next: troll_driven_evendorn

> 全場沉默了一瞬。
