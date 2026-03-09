"""CharacterBuilder 分步驟建角測試。"""

from __future__ import annotations

import pytest

from tot.gremlins.bone_engine.character import (
    CLASS_REGISTRY,
    CharacterBuilder,
)
from tot.models import Ability, AbilityScores, Skill


# ---------------------------------------------------------------------------
# 完整建角流程
# ---------------------------------------------------------------------------

class TestCharacterBuilderHappyPath:
    """正常流程：背景→種族→職業→屬性→技能→build。"""

    def test_full_build_fighter(self):
        builder = CharacterBuilder()
        builder.set_name("Theron")
        builder.set_background("soldier")
        builder.set_species("human")
        builder.set_class("Fighter")
        builder.set_ability_scores(
            AbilityScores(STR=16, DEX=14, CON=14, INT=10, WIS=12, CHA=10)
        )
        builder.set_skills([Skill.ATHLETICS, Skill.PERCEPTION])

        char = builder.build()

        assert char.name == "Theron"
        assert char.char_class == "Fighter"
        assert char.background == "soldier"
        assert char.species == "human"
        assert char.hp_max > 0
        assert char.ac > 0
        assert Skill.ATHLETICS in char.skill_proficiencies

    def test_full_build_wizard(self):
        builder = CharacterBuilder()
        builder.set_name("Gandalf")
        builder.set_background("sage")
        builder.set_species("elf")
        builder.set_class("Wizard")
        builder.set_ability_scores(
            AbilityScores(STR=8, DEX=14, CON=12, INT=16, WIS=13, CHA=10)
        )
        builder.set_skills([Skill.ARCANA, Skill.INVESTIGATION])

        char = builder.build()

        assert char.char_class == "Wizard"
        assert char.spell_slots.max_slots.get(1, 0) > 0  # Wizard has spell slots

    def test_full_build_with_armor(self):
        builder = CharacterBuilder()
        builder.set_name("Paladin")
        builder.set_background("noble")
        builder.set_species("human")
        builder.set_class("Paladin")
        builder.set_ability_scores(
            AbilityScores(STR=16, DEX=10, CON=14, INT=8, WIS=12, CHA=14)
        )
        builder.set_skills([Skill.ATHLETICS, Skill.PERSUASION])
        builder.set_armor("heavy", has_shield=True)

        char = builder.build()

        assert char.ac == 18  # 鏈甲 16 + 盾牌 2


# ---------------------------------------------------------------------------
# 步驟追蹤
# ---------------------------------------------------------------------------

class TestCurrentStep:
    """current_step 追蹤下一步。"""

    def test_step_progression(self):
        builder = CharacterBuilder()
        assert builder.current_step == "background"

        builder.set_background("criminal")
        assert builder.current_step == "species"

        builder.set_species("elf")
        assert builder.current_step == "class"

        builder.set_class("Rogue")
        assert builder.current_step == "ability_scores"

        builder.set_ability_scores(
            AbilityScores(STR=10, DEX=16, CON=12, INT=14, WIS=10, CHA=8)
        )
        assert builder.current_step == "skills"

        builder.set_skills([
            Skill.STEALTH, Skill.SLEIGHT_OF_HAND,
            Skill.PERCEPTION, Skill.DECEPTION,
        ])
        assert builder.current_step == "ready"


# ---------------------------------------------------------------------------
# 前置條件驗證
# ---------------------------------------------------------------------------

class TestPreconditions:
    """每個步驟的前置條件檢查。"""

    def test_species_before_background(self):
        builder = CharacterBuilder()
        with pytest.raises(ValueError, match="背景"):
            builder.set_species("elf")

    def test_class_before_species(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        with pytest.raises(ValueError, match="種族"):
            builder.set_class("Fighter")

    def test_ability_scores_before_class(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        with pytest.raises(ValueError, match="職業"):
            builder.set_ability_scores(AbilityScores())

    def test_skills_before_ability_scores(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        builder.set_class("Fighter")
        with pytest.raises(ValueError, match="屬性"):
            builder.set_skills([Skill.ATHLETICS])

    def test_build_incomplete(self):
        builder = CharacterBuilder()
        builder.set_name("Test")
        with pytest.raises(ValueError, match="尚未完成"):
            builder.build()

    def test_build_without_name(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        builder.set_class("Fighter")
        builder.set_ability_scores(AbilityScores())
        builder.set_skills([Skill.ATHLETICS, Skill.PERCEPTION])
        with pytest.raises(ValueError, match="名稱"):
            builder.build()

    def test_empty_name_rejected(self):
        builder = CharacterBuilder()
        with pytest.raises(ValueError, match="不能為空"):
            builder.set_name("   ")

    def test_cannot_set_background_twice(self):
        """背景設定後不能再設定一次。"""
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        with pytest.raises(ValueError, match="第一步"):
            builder.set_background("criminal")


# ---------------------------------------------------------------------------
# 職業驗證
# ---------------------------------------------------------------------------

class TestClassValidation:
    """職業相關驗證。"""

    def test_unknown_class_rejected(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        with pytest.raises(ValueError, match="未知職業"):
            builder.set_class("Artificer")

    def test_wrong_skill_for_class(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        builder.set_class("Fighter")
        builder.set_ability_scores(AbilityScores())
        with pytest.raises(ValueError, match="無法選擇"):
            builder.set_skills([Skill.ARCANA, Skill.PERCEPTION])

    def test_wrong_skill_count(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        builder.set_class("Fighter")
        builder.set_ability_scores(AbilityScores())
        with pytest.raises(ValueError, match="應選"):
            builder.set_skills([Skill.ATHLETICS])  # Fighter 需要 2 個


# ---------------------------------------------------------------------------
# 屬性值驗證
# ---------------------------------------------------------------------------

class TestAbilityScoreValidation:
    """屬性值分配驗證。"""

    def test_point_buy_valid(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        builder.set_class("Fighter")
        scores = {
            Ability.STR: 15, Ability.DEX: 14, Ability.CON: 13,
            Ability.INT: 12, Ability.WIS: 10, Ability.CHA: 8,
        }
        # 點數: 9+7+5+4+2+0 = 27 ✓
        builder.set_ability_scores(scores, method="point_buy")
        assert builder.current_step == "ability_scores" or builder.current_step == "skills"

    def test_point_buy_invalid(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        builder.set_class("Fighter")
        scores = {
            Ability.STR: 15, Ability.DEX: 15, Ability.CON: 15,
            Ability.INT: 15, Ability.WIS: 15, Ability.CHA: 15,
        }
        with pytest.raises(ValueError):
            builder.set_ability_scores(scores, method="point_buy")

    def test_standard_array_valid(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        builder.set_class("Fighter")
        scores = {
            Ability.STR: 15, Ability.DEX: 14, Ability.CON: 13,
            Ability.INT: 12, Ability.WIS: 10, Ability.CHA: 8,
        }
        builder.set_ability_scores(scores, method="standard_array")
        assert builder.current_step == "skills"


# ---------------------------------------------------------------------------
# 輔助查詢
# ---------------------------------------------------------------------------

class TestBuilderQueries:
    """available_classes / available_skills / num_skills 查詢。"""

    def test_available_classes(self):
        builder = CharacterBuilder()
        assert "Fighter" in builder.available_classes
        assert "Wizard" in builder.available_classes
        assert len(builder.available_classes) == 12

    def test_available_skills_empty_before_class(self):
        builder = CharacterBuilder()
        assert builder.available_skills == []

    def test_available_skills_after_class(self):
        builder = CharacterBuilder()
        builder.set_background("soldier")
        builder.set_species("human")
        builder.set_class("Rogue")
        assert Skill.STEALTH in builder.available_skills
        assert builder.num_skills == 4

    def test_level_validation(self):
        builder = CharacterBuilder()
        with pytest.raises(ValueError, match="1-20"):
            builder.set_level(0)
        with pytest.raises(ValueError, match="1-20"):
            builder.set_level(21)
