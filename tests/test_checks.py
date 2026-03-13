"""技能/屬性檢定單元測試。"""

from __future__ import annotations

import random

from tot.gremlins.bone_engine.checks import (
    CheckResult,
    ability_check,
    best_passive_perception,
    passive_skill,
    skill_check,
)
from tot.models import Ability, AbilityScores, Character, Skill

# ---------------------------------------------------------------------------
# 共用 fixtures
# ---------------------------------------------------------------------------


def _wizard() -> Character:
    """INT 18 Wizard，Investigation 熟練。"""
    return Character(
        name="陶德",
        char_class="Wizard",
        level=5,
        ability_scores=AbilityScores(STR=8, DEX=14, CON=12, INT=18, WIS=12, CHA=10),
        proficiency_bonus=3,
        hp_max=27,
        hp_current=27,
        skill_proficiencies=[Skill.ARCANA, Skill.INVESTIGATION],
    )


def _fighter() -> Character:
    """STR 16 Fighter，Athletics 熟練、Perception 熟練。"""
    return Character(
        name="Aldric",
        char_class="Fighter",
        level=5,
        ability_scores=AbilityScores(STR=16, DEX=12, CON=14, INT=10, WIS=12, CHA=8),
        proficiency_bonus=3,
        hp_max=44,
        hp_current=44,
        skill_proficiencies=[Skill.ATHLETICS, Skill.PERCEPTION],
    )


# ---------------------------------------------------------------------------
# skill_check 測試
# ---------------------------------------------------------------------------


class TestSkillCheck:
    def test_success(self):
        """檢定總值 >= DC → 成功。"""
        wizard = _wizard()
        # Investigation bonus = INT mod(+4) + proficiency(+3) = +7
        # rng seed 42: d20 = ? → 用固定 rng 確保 deterministic
        rng = random.Random(42)
        result = skill_check(wizard, Skill.INVESTIGATION, dc=10, rng=rng)
        assert isinstance(result, CheckResult)
        assert result.total == result.natural + 7
        assert result.dc == 10
        assert "Investigation" in result.label

    def test_failure_low_roll(self):
        """尋找一個讓檢定失敗的 seed。"""
        wizard = _wizard()
        # Investigation bonus = +7，DC 30 一定失敗（d20 最高 20+7=27）
        rng = random.Random(0)
        result = skill_check(wizard, Skill.INVESTIGATION, dc=30, rng=rng)
        assert result.success is False

    def test_exact_dc(self):
        """總值 == DC → 成功（D&D 規則：meets it beats it）。"""
        wizard = _wizard()
        # bonus = +7，先擲一次取得 natural，再以 natural+7 為 DC 重擲
        rng = random.Random(0)
        probe = skill_check(wizard, Skill.INVESTIGATION, dc=0, rng=rng)
        exact_dc = probe.natural + 7
        rng2 = random.Random(0)
        result = skill_check(wizard, Skill.INVESTIGATION, dc=exact_dc, rng=rng2)
        assert result.success is True
        assert result.total == exact_dc

    def test_unproficient_skill(self):
        """未熟練技能只加屬性修正。"""
        wizard = _wizard()
        # Perception (WIS) — 未熟練 → bonus = WIS mod(+1)
        rng = random.Random(42)
        result = skill_check(wizard, Skill.PERCEPTION, dc=10, rng=rng)
        assert result.total == result.natural + 1


# ---------------------------------------------------------------------------
# ability_check 測試
# ---------------------------------------------------------------------------


class TestAbilityCheck:
    def test_str_check(self):
        """STR 檢定加 STR modifier。"""
        fighter = _fighter()
        # STR 16 → mod +3
        rng = random.Random(42)
        result = ability_check(fighter, Ability.STR, dc=15, rng=rng)
        assert result.total == result.natural + 3
        assert "STR" in result.label

    def test_negative_modifier(self):
        """低屬性值產生負修正。"""
        wizard = _wizard()
        # STR 8 → mod -1
        rng = random.Random(42)
        result = ability_check(wizard, Ability.STR, dc=10, rng=rng)
        assert result.total == result.natural - 1


# ---------------------------------------------------------------------------
# passive_skill 測試
# ---------------------------------------------------------------------------


class TestPassiveSkill:
    def test_passive_perception(self):
        """被動感知 = 10 + Perception bonus。"""
        fighter = _fighter()
        # WIS 12 → mod +1, Perception 熟練 → +3 = total +4
        assert passive_skill(fighter, Skill.PERCEPTION) == 14

    def test_passive_investigation(self):
        """被動調查 = 10 + Investigation bonus。"""
        wizard = _wizard()
        # INT 18 → mod +4, Investigation 熟練 → +3 = total +7
        assert passive_skill(wizard, Skill.INVESTIGATION) == 17

    def test_matches_character_passive_perception(self):
        """passive_skill(PERCEPTION) 應與 Character.passive_perception 一致。"""
        fighter = _fighter()
        assert passive_skill(fighter, Skill.PERCEPTION) == fighter.passive_perception


# ---------------------------------------------------------------------------
# best_passive_perception 測試
# ---------------------------------------------------------------------------


class TestBestPassivePerception:
    def test_selects_highest(self):
        """從隊伍中選出最高被動感知。"""
        wizard = _wizard()  # passive = 10 + 1 = 11
        fighter = _fighter()  # passive = 10 + 4 = 14
        assert best_passive_perception([wizard, fighter]) == 14

    def test_empty_party(self):
        """空隊伍回傳 0。"""
        assert best_passive_perception([]) == 0

    def test_single_character(self):
        """單人隊伍回傳該角色的值。"""
        wizard = _wizard()
        assert best_passive_perception([wizard]) == wizard.passive_perception
