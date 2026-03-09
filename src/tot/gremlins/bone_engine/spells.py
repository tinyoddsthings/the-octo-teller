"""法術系統——資料庫載入、施法檢查、效果執行、專注管理。

Bone Engine 的法術處理核心：
- 法術資料庫從 JSON 載入
- can_cast() 施法前置檢查
- cast_spell() 效果執行（傷害/治療/狀態）
- 專注管理
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from tot.gremlins.bone_engine.combat import (
    apply_damage,
    break_concentration,
    resolve_attack,
    resolve_saving_throw,
    roll_damage,
)
from tot.gremlins.bone_engine.conditions import apply_condition
from tot.gremlins.bone_engine.dice import roll
from tot.models import (
    Ability,
    ActiveCondition,
    Character,
    DamageType,
    Monster,
    Spell,
    SpellAttackType,
    SpellEffectType,
)

# 生物型別別名
Combatant = Character | Monster

# ---------------------------------------------------------------------------
# 法術資料庫
# ---------------------------------------------------------------------------

_SPELL_DB: dict[str, Spell] = {}

_SPELLS_JSON = Path(__file__).resolve().parents[2] / "data" / "spells.json"


def load_spell_db(path: Path | None = None) -> dict[str, Spell]:
    """從 JSON 載入法術資料庫。回傳 {name: Spell} 字典。

    首次呼叫時載入並快取，後續呼叫直接回傳快取。
    傳入 path 可覆蓋預設路徑（用於測試）。
    """
    global _SPELL_DB  # noqa: PLW0603

    if _SPELL_DB and path is None:
        return _SPELL_DB

    source = path or _SPELLS_JSON
    raw = json.loads(source.read_text(encoding="utf-8"))
    db: dict[str, Spell] = {}
    for entry in raw:
        spell = Spell.model_validate(entry)
        db[spell.name] = spell
    _SPELL_DB = db
    return db


def get_spell_by_name(name: str) -> Spell | None:
    """依名稱查詢法術。支援中文名或英文名，不區分大小寫。"""
    db = load_spell_db()
    # 精確匹配中文名
    if name in db:
        return db[name]
    # 不區分大小寫搜尋中文名或英文名
    lower = name.lower()
    for spell in db.values():
        if spell.name.lower() == lower or spell.en_name.lower() == lower:
            return spell
    return None


def list_spells(
    *,
    level: int | None = None,
    char_class: str | None = None,
    school: str | None = None,
) -> list[Spell]:
    """列出符合條件的法術。"""
    db = load_spell_db()
    results = list(db.values())
    if level is not None:
        results = [s for s in results if s.level == level]
    if char_class is not None:
        results = [s for s in results if char_class in s.classes]
    if school is not None:
        lower = school.lower()
        results = [s for s in results if s.school.value.lower() == lower]
    return results


# ---------------------------------------------------------------------------
# 施法前置檢查
# ---------------------------------------------------------------------------


class CastError:
    """施法失敗原因。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __repr__(self) -> str:
        return f"CastError({self.reason!r})"


def can_cast(
    caster: Combatant,
    spell: Spell,
    *,
    slot_level: int | None = None,
) -> CastError | None:
    """檢查 caster 是否能施放 spell。回傳 None 表示可施放，CastError 表示不行。

    檢查項目：
    1. 戲法不消耗法術欄位
    2. 非戲法：slot_level >= spell.level，且有剩餘欄位
    3. 法術是否在已知/已準備列表中（Character 限定）
    """
    # 戲法不需要欄位
    if spell.level == 0:
        return None

    # 非戲法：需要法術欄位
    if not isinstance(caster, Character):
        return None  # Monster 不受欄位限制

    # slot_level=0 明確表示不提供欄位（非戲法不可用 0 環）
    if slot_level is not None and slot_level == 0:
        return CastError("非戲法不能用 0 環法術欄位施放")

    actual_slot = slot_level or spell.level
    if actual_slot < spell.level:
        return CastError(f"法術欄位等級 {actual_slot} 低於法術等級 {spell.level}")

    current = caster.spell_slots.current_slots.get(actual_slot, 0)
    if current <= 0:
        return CastError(f"沒有剩餘的 {actual_slot} 環法術欄位")

    # 是否已知/已準備
    name = spell.name
    known = caster.spells_known or []
    prepared = caster.spells_prepared or []
    if (known or prepared) and name not in known and name not in prepared:
        return CastError(f"法術 {name!r} 未在已知或已準備列表中")

    return None


# ---------------------------------------------------------------------------
# 法術效果執行
# ---------------------------------------------------------------------------


class CastResult:
    """施法結果。"""

    def __init__(
        self,
        *,
        success: bool,
        spell: Spell,
        slot_used: int = 0,
        damage_dealt: int = 0,
        healing_done: int = 0,
        condition_applied: ActiveCondition | None = None,
        concentration_started: bool = False,
        concentration_broken: str | None = None,
        save_passed: bool = False,
        message: str = "",
    ) -> None:
        self.success = success
        self.spell = spell
        self.slot_used = slot_used
        self.damage_dealt = damage_dealt
        self.healing_done = healing_done
        self.condition_applied = condition_applied
        self.concentration_started = concentration_started
        self.concentration_broken = concentration_broken
        self.save_passed = save_passed
        self.message = message


def cast_spell(
    caster: Combatant,
    spell: Spell,
    target: Combatant | None = None,
    *,
    slot_level: int | None = None,
    rng: random.Random | None = None,
) -> CastResult:
    """施放法術主函式。

    處理流程：
    1. can_cast 檢查
    2. 消耗法術欄位
    3. 處理專注（中斷舊的、開始新的）
    4. 依 effect_type 分支執行：
       - DAMAGE: 攻擊型或豁免型
       - HEALING: 治療
       - CONDITION: 施加狀態
       - BUFF: 增益
       - UTILITY: 非戰鬥
    """
    rng = rng or random.Random()
    actual_slot = slot_level or max(spell.level, 1)

    # 前置檢查
    error = can_cast(caster, spell, slot_level=actual_slot)
    if error is not None:
        return CastResult(success=False, spell=spell, message=error.reason)

    # 消耗法術欄位（戲法不消耗）
    if spell.level > 0 and isinstance(caster, Character):
        caster.spell_slots.use(actual_slot)

    # 專注管理
    concentration_broken: str | None = None
    concentration_started = False
    if spell.concentration:
        if isinstance(caster, Character) and caster.concentration_spell:
            concentration_broken = break_concentration(caster)
        if isinstance(caster, Character):
            caster.concentration_spell = spell.name
            concentration_started = True

    # 效果分支
    if spell.effect_type == SpellEffectType.DAMAGE:
        return _resolve_damage_spell(
            caster,
            spell,
            target,
            actual_slot=actual_slot,
            concentration_started=concentration_started,
            concentration_broken=concentration_broken,
            rng=rng,
        )

    if spell.effect_type == SpellEffectType.HEALING:
        return _resolve_healing_spell(
            caster,
            spell,
            target,
            actual_slot=actual_slot,
            concentration_started=concentration_started,
            concentration_broken=concentration_broken,
            rng=rng,
        )

    if spell.effect_type == SpellEffectType.CONDITION:
        return _resolve_condition_spell(
            caster,
            spell,
            target,
            actual_slot=actual_slot,
            concentration_started=concentration_started,
            concentration_broken=concentration_broken,
            rng=rng,
        )

    # BUFF / UTILITY — 目前只回傳成功訊息
    return CastResult(
        success=True,
        spell=spell,
        slot_used=actual_slot if spell.level > 0 else 0,
        concentration_started=concentration_started,
        concentration_broken=concentration_broken,
        message=f"{_caster_name(caster)} 施放了 {spell.name}！",
    )


# ---------------------------------------------------------------------------
# 傷害法術
# ---------------------------------------------------------------------------


def _resolve_damage_spell(
    caster: Combatant,
    spell: Spell,
    target: Combatant | None,
    *,
    actual_slot: int,
    concentration_started: bool,
    concentration_broken: str | None,
    rng: random.Random,
) -> CastResult:
    """處理傷害型法術（攻擊型或豁免型）。"""
    if target is None:
        return CastResult(success=False, spell=spell, message="傷害法術需要目標")

    upcast_levels = max(0, actual_slot - spell.level) if spell.level > 0 else 0
    damage_dice = _upcast_damage(spell.damage_dice, spell.upcast_dice, upcast_levels)

    # 法術攻擊（遠程或近戰）
    if spell.attack_type != SpellAttackType.NONE:
        return _resolve_attack_damage(
            caster,
            spell,
            target,
            damage_dice=damage_dice,
            actual_slot=actual_slot,
            concentration_started=concentration_started,
            concentration_broken=concentration_broken,
            rng=rng,
        )

    # 豁免型（save_ability 存在）
    if spell.save_ability is not None:
        return _resolve_save_damage(
            caster,
            spell,
            target,
            damage_dice=damage_dice,
            actual_slot=actual_slot,
            concentration_started=concentration_started,
            concentration_broken=concentration_broken,
            rng=rng,
        )

    # 自動命中（如 Magic Missile）
    total_damage = roll(damage_dice, rng=rng).total
    apply_damage(target, total_damage, spell.damage_type or DamageType.FORCE)
    return CastResult(
        success=True,
        spell=spell,
        slot_used=actual_slot if spell.level > 0 else 0,
        damage_dealt=total_damage,
        concentration_started=concentration_started,
        concentration_broken=concentration_broken,
        message=(
            f"{_caster_name(caster)} 施放 {spell.name}，"
            f"自動命中 {_target_name(target)}，造成 {total_damage} 點"
            f"{_damage_type_name(spell.damage_type)}傷害！"
        ),
    )


def _resolve_attack_damage(
    caster: Combatant,
    spell: Spell,
    target: Combatant,
    *,
    damage_dice: str,
    actual_slot: int,
    concentration_started: bool,
    concentration_broken: str | None,
    rng: random.Random,
) -> CastResult:
    """法術攻擊型傷害。"""
    attack_bonus = _spell_attack_bonus(caster)
    target_ac = target.ac

    attack_result = resolve_attack(
        attack_bonus=attack_bonus,
        target_ac=target_ac,
        rng=rng,
    )

    if not attack_result.is_hit:
        return CastResult(
            success=True,
            spell=spell,
            slot_used=actual_slot if spell.level > 0 else 0,
            concentration_started=concentration_started,
            concentration_broken=concentration_broken,
            message=(
                f"{_caster_name(caster)} 施放 {spell.name} 攻擊 "
                f"{_target_name(target)}——未命中！"
                f"（{attack_result.roll_result.total} vs AC {target_ac}）"
            ),
        )

    dmg_result = roll_damage(
        damage_dice,
        spell.damage_type or DamageType.FORCE,
        is_critical=attack_result.is_critical,
        rng=rng,
    )
    total_damage = dmg_result.total
    apply_damage(target, total_damage, spell.damage_type or DamageType.FORCE)

    # 附帶狀態（如 Ray of Sickness 命中時附加 Poisoned）
    condition_applied = None
    if spell.applies_condition is not None:
        condition_applied = apply_condition(
            target,
            spell.applies_condition,
            source=spell.name,
            remaining_rounds=1,
        )

    crit_text = "爆擊！" if attack_result.is_critical else ""
    return CastResult(
        success=True,
        spell=spell,
        slot_used=actual_slot if spell.level > 0 else 0,
        damage_dealt=total_damage,
        condition_applied=condition_applied,
        concentration_started=concentration_started,
        concentration_broken=concentration_broken,
        message=(
            f"{_caster_name(caster)} 施放 {spell.name} 命中 "
            f"{_target_name(target)}！{crit_text}"
            f"造成 {total_damage} 點{_damage_type_name(spell.damage_type)}傷害。"
        ),
    )


def _resolve_save_damage(
    caster: Combatant,
    spell: Spell,
    target: Combatant,
    *,
    damage_dice: str,
    actual_slot: int,
    concentration_started: bool,
    concentration_broken: str | None,
    rng: random.Random,
) -> CastResult:
    """豁免型傷害法術。"""
    dc = _spell_save_dc(caster)
    save_bonus = _get_save_bonus(target, spell.save_ability)

    save_result = resolve_saving_throw(
        save_bonus=save_bonus,
        dc=dc,
        ability=spell.save_ability,
        rng=rng,
    )

    if save_result.success:
        if spell.save_half:
            total_damage = roll(damage_dice, rng=rng).total // 2
            apply_damage(target, total_damage, spell.damage_type or DamageType.FORCE)
            return CastResult(
                success=True,
                spell=spell,
                slot_used=actual_slot if spell.level > 0 else 0,
                damage_dealt=total_damage,
                save_passed=True,
                concentration_started=concentration_started,
                concentration_broken=concentration_broken,
                message=(
                    f"{_caster_name(caster)} 施放 {spell.name}，"
                    f"{_target_name(target)} 豁免成功（半傷），"
                    f"受到 {total_damage} 點{_damage_type_name(spell.damage_type)}傷害。"
                ),
            )
        # 豁免成功且無半傷
        return CastResult(
            success=True,
            spell=spell,
            slot_used=actual_slot if spell.level > 0 else 0,
            save_passed=True,
            concentration_started=concentration_started,
            concentration_broken=concentration_broken,
            message=(
                f"{_caster_name(caster)} 施放 {spell.name}，"
                f"{_target_name(target)} 豁免成功，毫髮無傷！"
            ),
        )

    # 豁免失敗
    total_damage = roll(damage_dice, rng=rng).total
    apply_damage(target, total_damage, spell.damage_type or DamageType.FORCE)

    # 附帶狀態
    condition_applied = None
    if spell.applies_condition is not None:
        condition_applied = apply_condition(
            target,
            spell.applies_condition,
            source=spell.name,
            remaining_rounds=1,
        )

    return CastResult(
        success=True,
        spell=spell,
        slot_used=actual_slot if spell.level > 0 else 0,
        damage_dealt=total_damage,
        condition_applied=condition_applied,
        concentration_started=concentration_started,
        concentration_broken=concentration_broken,
        message=(
            f"{_caster_name(caster)} 施放 {spell.name}，"
            f"{_target_name(target)} 豁免失敗！"
            f"受到 {total_damage} 點{_damage_type_name(spell.damage_type)}傷害。"
        ),
    )


# ---------------------------------------------------------------------------
# 治療法術
# ---------------------------------------------------------------------------


def _resolve_healing_spell(
    caster: Combatant,
    spell: Spell,
    target: Combatant | None,
    *,
    actual_slot: int,
    concentration_started: bool,
    concentration_broken: str | None,
    rng: random.Random,
) -> CastResult:
    """處理治療型法術。"""
    heal_target = target or caster
    if not isinstance(heal_target, Character):
        return CastResult(success=False, spell=spell, message="治療法術只能作用於角色")

    upcast_levels = max(0, actual_slot - spell.level) if spell.level > 0 else 0
    healing_dice = _upcast_damage(spell.healing_dice, spell.upcast_dice, upcast_levels)

    healing = roll(healing_dice, rng=rng).total
    # 加上施法屬性調整值
    casting_mod = _casting_modifier(caster)
    healing += casting_mod

    # 實際治療
    old_hp = heal_target.hp_current
    heal_target.hp_current = min(heal_target.hp_max, old_hp + healing)
    actual_healing = heal_target.hp_current - old_hp

    return CastResult(
        success=True,
        spell=spell,
        slot_used=actual_slot if spell.level > 0 else 0,
        healing_done=actual_healing,
        concentration_started=concentration_started,
        concentration_broken=concentration_broken,
        message=(
            f"{_caster_name(caster)} 施放 {spell.name}，"
            f"{_target_name(heal_target)} 恢復 {actual_healing} 點生命值！"
            f"（{old_hp} → {heal_target.hp_current}/{heal_target.hp_max}）"
        ),
    )


# ---------------------------------------------------------------------------
# 狀態法術
# ---------------------------------------------------------------------------


def _resolve_condition_spell(
    caster: Combatant,
    spell: Spell,
    target: Combatant | None,
    *,
    actual_slot: int,
    concentration_started: bool,
    concentration_broken: str | None,
    rng: random.Random,
) -> CastResult:
    """處理純狀態型法術（需要豁免）。"""
    if target is None:
        return CastResult(success=False, spell=spell, message="狀態法術需要目標")

    # 有豁免的狀態法術
    if spell.save_ability is not None:
        dc = _spell_save_dc(caster)
        save_bonus = _get_save_bonus(target, spell.save_ability)

        save_result = resolve_saving_throw(
            save_bonus=save_bonus,
            dc=dc,
            ability=spell.save_ability,
            rng=rng,
        )

        if save_result.success:
            return CastResult(
                success=True,
                spell=spell,
                slot_used=actual_slot if spell.level > 0 else 0,
                save_passed=True,
                concentration_started=concentration_started,
                concentration_broken=concentration_broken,
                message=(
                    f"{_caster_name(caster)} 施放 {spell.name}，{_target_name(target)} 豁免成功！"
                ),
            )

    # 豁免失敗或無需豁免——施加狀態
    condition_applied = None
    if spell.applies_condition is not None:
        # 專注法術通常持續到專注中斷
        rounds = None if spell.concentration else 1
        condition_applied = apply_condition(
            target,
            spell.applies_condition,
            source=spell.name,
            remaining_rounds=rounds,
        )

    return CastResult(
        success=True,
        spell=spell,
        slot_used=actual_slot if spell.level > 0 else 0,
        condition_applied=condition_applied,
        concentration_started=concentration_started,
        concentration_broken=concentration_broken,
        message=(f"{_caster_name(caster)} 施放 {spell.name}，{_target_name(target)} 受到影響！"),
    )


# ---------------------------------------------------------------------------
# 專注管理（額外 API）
# ---------------------------------------------------------------------------


def start_concentration(caster: Character, spell_name: str) -> str | None:
    """開始專注。回傳被中斷的舊法術名稱（若有）。"""
    old = None
    if caster.concentration_spell:
        old = break_concentration(caster)
    caster.concentration_spell = spell_name
    return old


def is_concentrating(caster: Character) -> bool:
    """是否正在維持專注。"""
    return caster.concentration_spell is not None


# ---------------------------------------------------------------------------
# 內部輔助函式
# ---------------------------------------------------------------------------


def _caster_name(caster: Combatant) -> str:
    return caster.name


def _target_name(target: Combatant) -> str:
    return target.name


def _damage_type_name(dt: DamageType | None) -> str:
    return dt.value if dt else ""


def _spell_attack_bonus(caster: Combatant) -> int:
    """計算法術攻擊加值。"""
    if isinstance(caster, Character):
        return caster.spell_attack
    # Monster 預設用 proficiency + 最高心智屬性
    return 5


def _spell_save_dc(caster: Combatant) -> int:
    """計算法術豁免 DC。"""
    if isinstance(caster, Character):
        return caster.spell_dc
    # Monster 預設 DC
    return 13


def _casting_modifier(caster: Combatant) -> int:
    """取得施法屬性調整值。"""
    if isinstance(caster, Character):
        # spell_dc = 8 + prof + mod → mod = spell_dc - 8 - prof
        return caster.spell_dc - 8 - caster.proficiency_bonus
    return 3  # Monster 預設


def _get_save_bonus(target: Combatant, ability: Ability | None) -> int:
    """取得目標的豁免加值。"""
    if ability is None:
        return 0
    if isinstance(target, Character):
        return target.ability_scores.modifier(ability)
    if isinstance(target, Monster):
        return target.ability_scores.modifier(ability)
    return 0


def _upcast_damage(
    base_dice: str,
    upcast_dice: str,
    upcast_levels: int,
) -> str:
    """計算升環後的骰子表達式。

    roll() 只支援 "NdM+modifier" 格式，所以需要合併同面骰：
    例如 base="3d6", upcast="1d6", levels=2 → "5d6"
         base="3d4+3", upcast="1d4+1", levels=1 → "4d4+4"
    """
    if not upcast_dice or upcast_levels <= 0:
        return base_dice

    # 解析 NdM+modifier 格式
    import re

    def _parse_dice_expr(expr: str) -> tuple[int, int, int]:
        """回傳 (count, sides, modifier)。"""
        expr = expr.strip()
        m = re.match(r"^(\d*)d(\d+)(?:\+(\d+))?$", expr, re.IGNORECASE)
        if m:
            count = int(m.group(1)) if m.group(1) else 1
            sides = int(m.group(2))
            mod = int(m.group(3)) if m.group(3) else 0
            return count, sides, mod
        return 0, 0, 0

    bc, bs, bm = _parse_dice_expr(base_dice)
    uc, us, um = _parse_dice_expr(upcast_dice)

    if bc > 0 and uc > 0 and bs == us:
        # 同面骰——合併數量和修正值
        total_count = bc + uc * upcast_levels
        total_mod = bm + um * upcast_levels
        result = f"{total_count}d{bs}"
        if total_mod > 0:
            result += f"+{total_mod}"
        return result

    # 無法合併——回退為加法表達式
    parts = upcast_dice.lower().split("d")
    if len(parts) == 2:
        try:
            num = int(parts[0]) * upcast_levels
            die = parts[1]
            extra = f"{num}d{die}"
        except ValueError:
            extra = upcast_dice
    else:
        extra = "+".join([upcast_dice] * upcast_levels)

    if base_dice:
        return f"{base_dice}+{extra}"
    return extra
