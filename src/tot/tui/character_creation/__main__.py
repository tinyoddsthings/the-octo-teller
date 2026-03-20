"""角色建造 TUI 進入點：uv run python -m tot.tui.character_creation"""

from tot.tui.character_creation.app import CharacterCreationApp

app = CharacterCreationApp()
result = app.run()

if result is not None:
    print("\n═══ 建角完成 ═══")
    print(f"名稱：{result.name}")
    print(f"職業：{result.char_class}　背景：{result.background}　種族：{result.species}")
    print(f"HP: {result.hp_current}　AC: {result.ac}　被動感知: {result.passive_perception}")
    if result.skill_proficiencies:
        skills_str = ", ".join(s.value for s in result.skill_proficiencies)
        print(f"技能：{skills_str}")
