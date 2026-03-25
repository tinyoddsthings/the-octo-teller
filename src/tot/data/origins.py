"""2024 PHB (5.5e) 角色起源資料：16 背景 + 10 種族。

資料來源：docs/2024_translate/phb/ch4_character_origins.md
"""

from __future__ import annotations

from dataclasses import dataclass

from tot.models.enums import Ability, Skill, Tool, ToolCategory

# ─────────────────────────────────────────────────────────────────────────────
# 背景資料
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BackgroundData:
    """一個 PHB 背景的完整資料。"""

    id: str  # 英文 key（如 "Acolyte"）
    name_zh: str  # 中文名（如 "侍僧"）
    name_en: str  # 英文名
    description: str  # 1~2 句中文背景故事
    ability_tags: tuple[Ability, ...]  # 三項可調屬性（玩家從中選 +2/+1 或各 +1）
    feat: str  # 起源專長 id（如 "Magic Initiate: Cleric"）
    feat_zh: str  # 專長中文名
    skill_proficiencies: tuple[Skill, ...]  # 2 項固定技能
    tool_proficiency: str  # 工具顯示名稱（向後相容）
    equipment_a: str  # 裝備選項 A
    equipment_b: str = "50 GP"  # 裝備選項 B（固定 50 GP）
    tool_proficiency_enum: Tool | None = None  # 固定工具（型別安全）
    tool_proficiency_category: ToolCategory | None = None  # 「任選一種」的類別
    tool_proficiency_label: str = ""  # 顯示用（如「賭具（任選一種）」）


BACKGROUND_REGISTRY: dict[str, BackgroundData] = {
    "Acolyte": BackgroundData(
        id="Acolyte",
        name_zh="侍僧",
        name_en="Acolyte",
        description="你在神殿中奉獻自己，在祭司手下服務並研習宗教，學會了引導少許神聖力量。",
        ability_tags=(Ability.INT, Ability.WIS, Ability.CHA),
        feat="Magic Initiate: Cleric",
        feat_zh="魔法新手：牧師",
        skill_proficiencies=(Skill.INSIGHT, Skill.RELIGION),
        tool_proficiency="書法工具",
        equipment_a="書法工具、書籍（禱文）、聖徽、羊皮紙×10、長袍、8 GP",
        tool_proficiency_enum=Tool.CALLIGRAPHER_SUPPLIES,
    ),
    "Artisan": BackgroundData(
        id="Artisan",
        name_zh="工匠",
        name_en="Artisan",
        description="你從小在工匠工坊裡學手藝，磨練出敏銳觀察力與基本製作技能。",
        ability_tags=(Ability.STR, Ability.DEX, Ability.INT),
        feat="Crafter",
        feat_zh="製作者",
        skill_proficiencies=(Skill.INVESTIGATION, Skill.PERSUASION),
        tool_proficiency="工匠工具（任選一種）",
        equipment_a="工匠工具、小袋×2、旅行者服裝、32 GP",
        tool_proficiency_category=ToolCategory.ARTISAN,
        tool_proficiency_label="工匠工具（任選一種）",
    ),
    "Charlatan": BackgroundData(
        id="Charlatan",
        name_zh="騙徒",
        name_en="Charlatan",
        description="你在酒館間穿梭，學會欺騙那些尋求安慰謊言的可憐蟲——假藥水、偽造文件。",
        ability_tags=(Ability.DEX, Ability.CON, Ability.CHA),
        feat="Skilled",
        feat_zh="博學",
        skill_proficiencies=(Skill.DECEPTION, Skill.SLEIGHT_OF_HAND),
        tool_proficiency="偽造工具組",
        equipment_a="偽造工具組、戲服、華服、15 GP",
        tool_proficiency_enum=Tool.FORGERY_KIT,
    ),
    "Criminal": BackgroundData(
        id="Criminal",
        name_zh="罪犯",
        name_en="Criminal",
        description="你在暗巷中勉強求生，扒竊或入室行竊，也許與犯罪團夥合作，也許獨來獨往。",
        ability_tags=(Ability.DEX, Ability.CON, Ability.INT),
        feat="Alert",
        feat_zh="警覺",
        skill_proficiencies=(Skill.SLEIGHT_OF_HAND, Skill.STEALTH),
        tool_proficiency="盜賊工具",
        equipment_a="匕首×2、盜賊工具、撬棍、小袋×2、旅行者服裝、16 GP",
        tool_proficiency_enum=Tool.THIEVES_TOOLS,
    ),
    "Entertainer": BackgroundData(
        id="Entertainer",
        name_zh="藝人",
        name_en="Entertainer",
        description="你跟隨巡迴集市和嘉年華長大，學會了走鋼索、彈魯特琴或朗誦詩歌，渴望掌聲。",
        ability_tags=(Ability.STR, Ability.DEX, Ability.CHA),
        feat="Musician",
        feat_zh="樂師",
        skill_proficiencies=(Skill.ACROBATICS, Skill.PERFORMANCE),
        tool_proficiency="樂器（任選一種）",
        equipment_a="樂器、戲服×2、鏡子、香水、旅行者服裝、11 GP",
        tool_proficiency_category=ToolCategory.MUSICAL,
        tool_proficiency_label="樂器（任選一種）",
    ),
    "Farmer": BackgroundData(
        id="Farmer",
        name_zh="農夫",
        name_en="Farmer",
        description="你在田野間長大，多年照料動物和耕種讓你獲得了耐心和良好體質。",
        ability_tags=(Ability.STR, Ability.CON, Ability.WIS),
        feat="Tough",
        feat_zh="堅韌",
        skill_proficiencies=(Skill.ANIMAL_HANDLING, Skill.NATURE),
        tool_proficiency="木匠工具",
        equipment_a="鐮刀、木匠工具、治療工具包、鐵鍋、鏟子、旅行者服裝、30 GP",
        tool_proficiency_enum=Tool.CARPENTER_TOOLS,
    ),
    "Guard": BackgroundData(
        id="Guard",
        name_zh="守衛",
        name_en="Guard",
        description="你被訓練在塔樓上站崗，一隻眼看城外的掠奪者，另一隻眼看城內的扒手。",
        ability_tags=(Ability.STR, Ability.INT, Ability.WIS),
        feat="Alert",
        feat_zh="警覺",
        skill_proficiencies=(Skill.ATHLETICS, Skill.PERCEPTION),
        tool_proficiency="賭具（任選一種）",
        equipment_a="矛、輕弩、弩箭×20、賭具、附蓋提燈、手銬、箭袋、旅行者服裝、12 GP",
        tool_proficiency_category=ToolCategory.GAMING,
        tool_proficiency_label="賭具（任選一種）",
    ),
    "Guide": BackgroundData(
        id="Guide",
        name_zh="嚮導",
        name_en="Guide",
        description="你在戶外長大，遠離定居的土地，探索荒野奇蹟的過程中學會了照顧自己。",
        ability_tags=(Ability.DEX, Ability.CON, Ability.WIS),
        feat="Magic Initiate: Druid",
        feat_zh="魔法新手：德魯伊",
        skill_proficiencies=(Skill.STEALTH, Skill.SURVIVAL),
        tool_proficiency="製圖工具",
        equipment_a="短弓、箭×20、製圖工具、睡袋、箭袋、帳篷、旅行者服裝、3 GP",
        tool_proficiency_enum=Tool.CARTOGRAPHER_TOOLS,
    ),
    "Hermit": BackgroundData(
        id="Hermit",
        name_zh="隱士",
        name_en="Hermit",
        description="你在遠離聚落的小屋或修道院中隱居，花許多時間思索造物的奧秘。",
        ability_tags=(Ability.CON, Ability.WIS, Ability.CHA),
        feat="Healer",
        feat_zh="治療者",
        skill_proficiencies=(Skill.MEDICINE, Skill.RELIGION),
        tool_proficiency="草藥工具",
        equipment_a="長棍、草藥工具、睡袋、書籍（哲學）、油燈、燈油×3、旅行者服裝、16 GP",
        tool_proficiency_enum=Tool.HERBALISM_KIT,
    ),
    "Merchant": BackgroundData(
        id="Merchant",
        name_zh="商人",
        name_en="Merchant",
        description="你學習商業基礎，廣泛旅行，通過買賣原材料或成品來謀生。",
        ability_tags=(Ability.CON, Ability.INT, Ability.CHA),
        feat="Lucky",
        feat_zh="幸運",
        skill_proficiencies=(Skill.ANIMAL_HANDLING, Skill.PERSUASION),
        tool_proficiency="領航工具",
        equipment_a="領航工具、小袋×2、旅行者服裝、22 GP",
        tool_proficiency_enum=Tool.NAVIGATOR_TOOLS,
    ),
    "Noble": BackgroundData(
        id="Noble",
        name_zh="貴族",
        name_en="Noble",
        description="你在城堡中長大，被財富和特權包圍，接受一流教育並學會了領導。",
        ability_tags=(Ability.STR, Ability.INT, Ability.CHA),
        feat="Skilled",
        feat_zh="博學",
        skill_proficiencies=(Skill.HISTORY, Skill.PERSUASION),
        tool_proficiency="賭具（任選一種）",
        equipment_a="賭具、華服、香水、29 GP",
        tool_proficiency_category=ToolCategory.GAMING,
        tool_proficiency_label="賭具（任選一種）",
    ),
    "Sage": BackgroundData(
        id="Sage",
        name_zh="學者",
        name_en="Sage",
        description="你在莊園和修道院間遊歷，在漫長夜晚研讀書籍學習多元宇宙的學問。",
        ability_tags=(Ability.CON, Ability.INT, Ability.WIS),
        feat="Magic Initiate: Wizard",
        feat_zh="魔法新手：法師",
        skill_proficiencies=(Skill.ARCANA, Skill.HISTORY),
        tool_proficiency="書法工具",
        equipment_a="長棍、書法工具、書籍（歷史）、羊皮紙×8、長袍、8 GP",
        tool_proficiency_enum=Tool.CALLIGRAPHER_SUPPLIES,
    ),
    "Sailor": BackgroundData(
        id="Sailor",
        name_zh="水手",
        name_en="Sailor",
        description="你是海上的人，風在背後，甲板在腳下搖晃，面對過強大的風暴。",
        ability_tags=(Ability.STR, Ability.DEX, Ability.WIS),
        feat="Tavern Brawler",
        feat_zh="酒館鬥毆者",
        skill_proficiencies=(Skill.ACROBATICS, Skill.PERCEPTION),
        tool_proficiency="領航工具",
        equipment_a="匕首、領航工具、繩索、旅行者服裝、20 GP",
        tool_proficiency_enum=Tool.NAVIGATOR_TOOLS,
    ),
    "Scribe": BackgroundData(
        id="Scribe",
        name_zh="抄寫員",
        name_en="Scribe",
        description="你在抄經室或政府機關中學會了以清晰筆跡書寫，擁有對細節的專注力。",
        ability_tags=(Ability.DEX, Ability.INT, Ability.WIS),
        feat="Skilled",
        feat_zh="博學",
        skill_proficiencies=(Skill.INVESTIGATION, Skill.PERCEPTION),
        tool_proficiency="書法工具",
        equipment_a="書法工具、華服、油燈、燈油×3、羊皮紙×12、23 GP",
        tool_proficiency_enum=Tool.CALLIGRAPHER_SUPPLIES,
    ),
    "Soldier": BackgroundData(
        id="Soldier",
        name_zh="士兵",
        name_en="Soldier",
        description="你成年後就開始接受戰鬥訓練，對拿起武器之前的生活幾乎沒有記憶。",
        ability_tags=(Ability.STR, Ability.DEX, Ability.CON),
        feat="Savage Attacker",
        feat_zh="野蠻打擊者",
        skill_proficiencies=(Skill.ATHLETICS, Skill.INTIMIDATION),
        tool_proficiency="賭具（任選一種）",
        equipment_a="矛、短弓、箭×20、賭具、治療工具包、箭袋、旅行者服裝、14 GP",
        tool_proficiency_category=ToolCategory.GAMING,
        tool_proficiency_label="賭具（任選一種）",
    ),
    "Wayfarer": BackgroundData(
        id="Wayfarer",
        name_zh="流浪者",
        name_en="Wayfarer",
        description="你在街頭長大，做零工換食物，有時不得不偷竊，但從未失去尊嚴和希望。",
        ability_tags=(Ability.DEX, Ability.WIS, Ability.CHA),
        feat="Lucky",
        feat_zh="幸運",
        skill_proficiencies=(Skill.INSIGHT, Skill.STEALTH),
        tool_proficiency="盜賊工具",
        equipment_a="匕首×2、盜賊工具、賭具（任選）、睡袋、小袋×2、旅行者服裝、16 GP",
        tool_proficiency_enum=Tool.THIEVES_TOOLS,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# 種族資料
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LineageOption:
    """種族的血統/先祖子選項（如精靈的卓爾/高等/木精靈）。"""

    id: str
    name_zh: str
    name_en: str
    description: str  # 簡要效果說明


@dataclass(frozen=True)
class SpeciesData:
    """一個 PHB 種族的完整資料。"""

    id: str
    name_zh: str
    name_en: str
    description: str  # 1~2 句中文說明
    size: str  # "中型" / "小型" / "中型或小型"
    speed: str  # "9m" / "10.5m"
    traits: tuple[str, ...]  # 特性名稱清單
    traits_description: str  # 特性簡述
    lineage_options: tuple[LineageOption, ...] = ()  # 血統子選項
    skill_choice_count: int = 0  # Human 多才：自選技能熟練數
    feat_choice_count: int = 0  # Human 多藝：自選起源專長數


SPECIES_REGISTRY: dict[str, SpeciesData] = {
    "Aasimar": SpeciesData(
        id="Aasimar",
        name_zh="神裔",
        name_en="Aasimar",
        description="靈魂中攜帶上層位面火花的凡人，能燃起光明、治癒和天國之怒。壽命約 160 年。",
        size="中型或小型",
        speed="9m",
        traits=("天界抗性", "暗視", "治癒之觸", "光明使者", "天界啟示"),
        traits_description=(
            "黯蝕與光輝傷害抗性。18m 暗視。"
            "治癒之觸：魔法動作觸碰治療（熟練加值顆 d4），長休恢復。"
            "光亮術戲法（CHA）。"
            "3 級起可變身（天堂之翼/內在光輝/黯蝕帷幕），每回合造成額外傷害。"
        ),
        lineage_options=(
            LineageOption(
                id="heavenly_wings",
                name_zh="天堂之翼",
                name_en="Heavenly Wings",
                description="變身獲得飛行速度，額外光輝傷害。",
            ),
            LineageOption(
                id="inner_radiance",
                name_zh="內在光輝",
                name_en="Inner Radiance",
                description="散發灼熱光芒，3m 內每回合造成光輝傷害。",
            ),
            LineageOption(
                id="necrotic_shroud",
                name_zh="黯蝕帷幕",
                name_en="Necrotic Shroud",
                description="3m 內非盟友需魅力豁免否則驚懼，額外黯蝕傷害。",
            ),
        ),
    ),
    "Dragonborn": SpeciesData(
        id="Dragonborn",
        name_zh="龍裔",
        name_en="Dragonborn",
        description="龍族後裔，無翼雙足龍外貌，有鱗片、角和龍息。",
        size="中型",
        speed="9m",
        traits=("龍族先祖", "龍息武器", "傷害抗性", "暗視", "龍翼飛行"),
        traits_description=(
            "選擇龍族先祖決定傷害類型與抗性。"
            "龍息武器：4.5m 錐形或 9m 直線，1d10 傷害（5/11/17 級增加）。"
            "18m 暗視。5 級起可獲龍翼飛行（長休恢復）。"
        ),
        lineage_options=(
            LineageOption("black", "黑龍", "Black", "強酸傷害"),
            LineageOption("blue", "藍龍", "Blue", "閃電傷害"),
            LineageOption("brass", "黃銅龍", "Brass", "火焰傷害"),
            LineageOption("bronze", "青銅龍", "Bronze", "閃電傷害"),
            LineageOption("copper", "紅銅龍", "Copper", "強酸傷害"),
            LineageOption("gold", "金龍", "Gold", "火焰傷害"),
            LineageOption("green", "綠龍", "Green", "毒素傷害"),
            LineageOption("red", "紅龍", "Red", "火焰傷害"),
            LineageOption("silver", "銀龍", "Silver", "寒冷傷害"),
            LineageOption("white", "白龍", "White", "寒冷傷害"),
        ),
    ),
    "Dwarf": SpeciesData(
        id="Dwarf",
        name_zh="矮人",
        name_en="Dwarf",
        description="由鍛造之神從大地中喚起，如山脈般堅韌。壽命約 350 年。",
        size="中型",
        speed="9m",
        traits=("暗視", "矮人韌性", "矮人堅韌", "石知"),
        traits_description=(
            "36m 暗視（比一般種族遠）。"
            "毒素傷害抗性，避免/結束中毒豁免有優勢。"
            "矮人堅韌：最大 HP 每級 +1。"
            "石知：附贈動作獲得 18m 震顫感知（站在石面上），熟練加值次/長休。"
        ),
    ),
    "Elf": SpeciesData(
        id="Elf",
        name_zh="精靈",
        name_en="Elf",
        description="由神祇乩靈創造的優雅生物，有尖耳且不需睡眠。壽命約 750 年。",
        size="中型",
        speed="9m",
        traits=("暗視", "精靈血統", "妖精血脈", "敏銳感官", "冥想"),
        traits_description=(
            "18m 暗視。"
            "精靈血統：依血統獲得戲法 + 3/5 級法術。"
            "妖精血脈：避免/結束魅惑豁免有優勢。"
            "敏銳感官：洞察/觀察/求生三選一熟練。"
            "冥想：4 小時冥想替代睡眠完成長休。"
        ),
        lineage_options=(
            LineageOption(
                "drow",
                "卓爾",
                "Drow",
                "暗視增至 36m，舞光術戲法。3 級妖火術、5 級黑暗術。",
            ),
            LineageOption(
                "high_elf",
                "高等精靈",
                "High Elf",
                "幻術戲法（長休可換）。3 級偵測魔法、5 級迷蹤步。",
            ),
            LineageOption(
                "wood_elf",
                "木精靈",
                "Wood Elf",
                "速度增至 10.5m，德魯伊工藝戲法。3 級大步奔行、5 級行蹤無跡。",
            ),
        ),
    ),
    "Gnome": SpeciesData(
        id="Gnome",
        name_zh="侏儒",
        name_en="Gnome",
        description="魔法生物，大眼尖耳，用聰明才智彌補體型不足。壽命約 425 年。",
        size="小型",
        speed="9m",
        traits=("暗視", "侏儒狡詐", "侏儒血統"),
        traits_description=(
            "18m 暗視。侏儒狡詐：INT/WIS/CHA 豁免有優勢。侏儒血統：依血統獲得不同魔法能力。"
        ),
        lineage_options=(
            LineageOption(
                "forest_gnome",
                "森林侏儒",
                "Forest Gnome",
                "弱效幻象戲法。動物交談永備（熟練加值次/長休免費施放）。",
            ),
            LineageOption(
                "rock_gnome",
                "岩地侏儒",
                "Rock Gnome",
                "修復術和幻術戲法。可用幻術創造微型發條裝置。",
            ),
        ),
    ),
    "Goliath": SpeciesData(
        id="Goliath",
        name_zh="哥利雅",
        name_en="Goliath",
        description="巨人的遠親後裔，高大強壯，承載第一批巨人的超自然恩賜。",
        size="中型",
        speed="10.5m",
        traits=("巨人先祖", "巨大化", "強力體格"),
        traits_description=(
            "巨人先祖：選擇一種巨人恩賜（雲/火/冰/丘/石/風暴），熟練加值次/長休。"
            "巨大化（5 級起）：附贈動作變大型 10 分鐘，力量檢定優勢，速度 +3m。"
            "強力體格：結束擒抱檢定優勢，負重視為大一號。"
        ),
        lineage_options=(
            LineageOption("cloud", "雲巨人", "Cloud's Jaunt", "附贈動作傳送至 9m 內。"),
            LineageOption("fire", "火巨人", "Fire's Burn", "命中時額外 1d10 火焰傷害。"),
            LineageOption("frost", "冰巨人", "Frost's Chill", "命中時額外 1d6 寒冷傷害，降速 3m。"),
            LineageOption("hill", "丘巨人", "Hill's Tumble", "命中大型或更小生物可使其倒地。"),
            LineageOption("stone", "石巨人", "Stone's Endurance", "受傷時反應擲 1d12+CON 減傷。"),
            LineageOption(
                "storm", "風暴巨人", "Storm's Thunder", "18m 內生物對你造傷時反應 1d8 雷鳴。"
            ),
        ),
    ),
    "Halfling": SpeciesData(
        id="Halfling",
        name_zh="半身人",
        name_en="Halfling",
        description="嬌小的田園族群，擁有傳說中的「半身人之運」。壽命約 150 年。",
        size="小型",
        speed="9m",
        traits=("勇敢", "半身人靈巧", "幸運", "天生隱匿"),
        traits_description=(
            "勇敢：避免/結束驚懼豁免有優勢。"
            "半身人靈巧：可穿過比你大一號生物的空間。"
            "幸運：d20 骰出自然 1 可重骰，必須用新結果。"
            "天生隱匿：被大一號生物遮擋即可隱匿。"
        ),
    ),
    "Human": SpeciesData(
        id="Human",
        name_zh="人類",
        name_en="Human",
        description="遍布多元宇宙，種類繁多，在有限歲月裡盡力達成所能。",
        size="中型或小型",
        speed="9m",
        traits=("靈感英雄", "多才", "多藝"),
        traits_description=(
            "靈感英雄：每次長休獲得英雄靈感。"
            "多才：獲得一項自選技能熟練。"
            "多藝：獲得一個自選起源專長（建議博學）。"
        ),
        skill_choice_count=1,
        feat_choice_count=1,
    ),
    "Orc": SpeciesData(
        id="Orc",
        name_zh="獸人",
        name_en="Orc",
        description="古魯什神的孩子，裝備了穿越廣闊平原和面對怪物的禮物。",
        size="中型",
        speed="9m",
        traits=("腎上腺素衝刺", "暗視", "堅韌不拔"),
        traits_description=(
            "腎上腺素衝刺：附贈動作衝刺+臨時 HP（熟練加值次/短休或長休）。"
            "36m 暗視。"
            "堅韌不拔：HP 降至 0 時改為 1 HP（長休恢復）。"
        ),
    ),
    "Tiefling": SpeciesData(
        id="Tiefling",
        name_zh="提夫林",
        name_en="Tiefling",
        description="血統源自下層位面的魔裔後代，與魔鬼、惡魔或其他邪魔有血緣關係。",
        size="中型或小型",
        speed="9m",
        traits=("暗視", "魔裔傳承", "異界風采"),
        traits_description=(
            "18m 暗視。魔裔傳承：依傳承獲得傷害抗性+戲法+3/5 級法術。異界風采：奇術戲法。"
        ),
        lineage_options=(
            LineageOption(
                "abyssal",
                "深淵",
                "Abyssal",
                "毒素傷害抗性，毒霧術戲法。3 級疫病射線、5 級定身術。",
            ),
            LineageOption(
                "chthonic",
                "冥界",
                "Chthonic",
                "黯蝕傷害抗性，冷凍之觸戲法。3 級偽死術、5 級虛弱射線。",
            ),
            LineageOption(
                "infernal",
                "煉獄",
                "Infernal",
                "火焰傷害抗性，火焰箭戲法。3 級地獄斥責、5 級黑暗術。",
            ),
        ),
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# 技能中文名對照
# ─────────────────────────────────────────────────────────────────────────────

SKILL_ZH: dict[Skill, str] = {
    Skill.ATHLETICS: "運動",
    Skill.ACROBATICS: "特技動作",
    Skill.SLEIGHT_OF_HAND: "巧手",
    Skill.STEALTH: "隱藏",
    Skill.ARCANA: "奧法",
    Skill.HISTORY: "歷史",
    Skill.INVESTIGATION: "調查",
    Skill.NATURE: "自然",
    Skill.RELIGION: "宗教",
    Skill.ANIMAL_HANDLING: "馴服動物",
    Skill.INSIGHT: "洞察",
    Skill.MEDICINE: "醫術",
    Skill.PERCEPTION: "觀察",
    Skill.SURVIVAL: "求生",
    Skill.DECEPTION: "欺騙",
    Skill.INTIMIDATION: "威嚇",
    Skill.PERFORMANCE: "表演",
    Skill.PERSUASION: "說服",
}

TOOL_ZH: dict[Tool, str] = {
    # 工匠工具
    Tool.ALCHEMIST_SUPPLIES: "煉金工具",
    Tool.BREWER_SUPPLIES: "釀造工具",
    Tool.CALLIGRAPHER_SUPPLIES: "書法工具",
    Tool.CARPENTER_TOOLS: "木匠工具",
    Tool.CARTOGRAPHER_TOOLS: "製圖工具",
    Tool.COBBLER_TOOLS: "鞋匠工具",
    Tool.COOK_UTENSILS: "烹飪用具",
    Tool.GLASSBLOWER_TOOLS: "吹玻璃工具",
    Tool.JEWELER_TOOLS: "珠寶匠工具",
    Tool.LEATHERWORKER_TOOLS: "皮革匠工具",
    Tool.MASON_TOOLS: "石匠工具",
    Tool.PAINTER_SUPPLIES: "畫具",
    Tool.POTTER_TOOLS: "陶匠工具",
    Tool.SMITH_TOOLS: "鐵匠工具",
    Tool.TINKER_TOOLS: "修補匠工具",
    Tool.WEAVER_TOOLS: "織工工具",
    Tool.WOODCARVER_TOOLS: "木雕工具",
    # 遊戲組
    Tool.DICE_SET: "骰子組",
    Tool.DRAGONCHESS_SET: "龍棋組",
    Tool.PLAYING_CARDS: "撲克牌",
    Tool.THREE_DRAGON_ANTE: "三龍賭牌組",
    # 樂器
    Tool.BAGPIPES: "風笛",
    Tool.DRUM: "鼓",
    Tool.DULCIMER: "揚琴",
    Tool.FLUTE: "長笛",
    Tool.HORN: "號角",
    Tool.LUTE: "魯特琴",
    Tool.LYRE: "里拉琴",
    Tool.PAN_FLUTE: "排笛",
    Tool.SHAWM: "蕭姆管",
    Tool.VIOL: "維奧爾琴",
    # 其他
    Tool.DISGUISE_KIT: "易容工具",
    Tool.FORGERY_KIT: "偽造工具組",
    Tool.HERBALISM_KIT: "草藥工具",
    Tool.NAVIGATOR_TOOLS: "領航工具",
    Tool.POISONER_KIT: "毒藥工具",
    Tool.THIEVES_TOOLS: "盜賊工具",
}


@dataclass(frozen=True)
class ToolInfo:
    """工具描述資料。來源：PHB ch6。"""

    ability: str  # 能力（中文，如「智力」「敏捷」）
    utilize: str  # 運用動作描述
    craft: str = ""  # 可製作物品（部分工具沒有）


TOOL_DATA: dict[Tool, ToolInfo] = {
    # ── 工匠工具 ──
    Tool.ALCHEMIST_SUPPLIES: ToolInfo(
        ability="智力",
        utilize="鑑定某種物質（DC 15），或生火（DC 15）",
        craft="強酸、煉金火、材料袋、油、紙、香水",
    ),
    Tool.BREWER_SUPPLIES: ToolInfo(
        ability="智力",
        utilize="偵測被下毒的飲料（DC 15），或鑑定酒類（DC 10）",
        craft="萬解藥",
    ),
    Tool.CALLIGRAPHER_SUPPLIES: ToolInfo(
        ability="敏捷",
        utilize="以華麗筆跡書寫文字以防偽造（DC 15）",
        craft="墨水、法術卷軸",
    ),
    Tool.CARPENTER_TOOLS: ToolInfo(
        ability="力量",
        utilize="封閉或撬開門或容器（DC 20）",
        craft="棍棒、巨棒、木棍、桶、箱子、梯子、桿、攜帶式衝撞槌、火把",
    ),
    Tool.CARTOGRAPHER_TOOLS: ToolInfo(
        ability="感知",
        utilize="繪製小區域的地圖（DC 15）",
        craft="地圖",
    ),
    Tool.COBBLER_TOOLS: ToolInfo(
        ability="敏捷",
        utilize="修改鞋子，使穿戴者的下一次敏捷（特技動作）檢定具有優勢（DC 10）",
        craft="攀爬工具包",
    ),
    Tool.COOK_UTENSILS: ToolInfo(
        ability="感知",
        utilize="改善食物風味（DC 10），或偵測腐壞或被下毒的食物（DC 15）",
        craft="口糧",
    ),
    Tool.GLASSBLOWER_TOOLS: ToolInfo(
        ability="智力",
        utilize="辨別玻璃物品在過去 24 小時內盛裝過什麼（DC 15）",
        craft="玻璃瓶、放大鏡、望遠鏡、小瓶",
    ),
    Tool.JEWELER_TOOLS: ToolInfo(
        ability="智力",
        utilize="辨別寶石的價值（DC 15）",
        craft="奧術法器、聖徽",
    ),
    Tool.LEATHERWORKER_TOOLS: ToolInfo(
        ability="敏捷",
        utilize="在皮革製品上加上設計圖案（DC 10）",
        craft="投石索、鞭、獸皮甲、皮甲、鑲釘皮甲、背包、弩矢盒、地圖或卷軸盒、羊皮紙、小袋、箭袋、水袋",
    ),
    Tool.MASON_TOOLS: ToolInfo(
        ability="力量",
        utilize="在石頭上鑿刻符號或孔洞（DC 10）",
        craft="滑輪組",
    ),
    Tool.PAINTER_SUPPLIES: ToolInfo(
        ability="感知",
        utilize="畫出你見過的事物的辨識圖像（DC 10）",
        craft="德魯伊法器、聖徽",
    ),
    Tool.POTTER_TOOLS: ToolInfo(
        ability="智力",
        utilize="辨別陶瓷物品在過去 24 小時內盛裝過什麼（DC 15）",
        craft="水壺、油燈",
    ),
    Tool.SMITH_TOOLS: ToolInfo(
        ability="力量",
        utilize="撬開門或容器（DC 20）",
        craft="任何近戰武器（棍棒、巨棒、木棍和鞭除外）、中甲（獸皮甲除外）、重甲、滾珠、桶、鐵蒺藜、鏈條、撬棍、火器子彈、抓鈎、鐵鍋、鐵釘、投石子彈",
    ),
    Tool.TINKER_TOOLS: ToolInfo(
        ability="敏捷",
        utilize="用廢料組裝一個微型物品，1 分鐘後散架（DC 20）",
        craft="火槍、手槍、鈴鐺、牛眼提燈、酒壺、帶罩提燈、捕獸夾、鎖、枷鎖、鏡子、鏟子、信號哨、火種盒",
    ),
    Tool.WEAVER_TOOLS: ToolInfo(
        ability="敏捷",
        utilize="修補衣物上的破洞（DC 10），或縫製一個微型圖案（DC 10）",
        craft="綿甲、籃子、睡袋、毯子、華服、網、長袍、繩子、麻袋、細繩、帳篷、旅行者服裝",
    ),
    Tool.WOODCARVER_TOOLS: ToolInfo(
        ability="敏捷",
        utilize="在木頭上雕刻圖案（DC 10）",
        craft="棍棒、巨棒、木棍、遠程武器（手槍、火槍和投石索除外）、奧術法器、箭矢、弩矢、德魯伊法器、墨水筆、吹針",
    ),
    # ── 其他工具 ──
    Tool.DISGUISE_KIT: ToolInfo(
        ability="魅力",
        utilize="化妝（DC 10）",
        craft="戲服",
    ),
    Tool.FORGERY_KIT: ToolInfo(
        ability="敏捷",
        utilize="模仿他人的 10 個字以內的筆跡（DC 15），或複製蠟封（DC 20）",
    ),
    Tool.HERBALISM_KIT: ToolInfo(
        ability="智力",
        utilize="辨認植物（DC 10）",
        craft="萬解藥、蠟燭、治療工具包、治療藥水",
    ),
    Tool.NAVIGATOR_TOOLS: ToolInfo(
        ability="感知",
        utilize="規劃航線（DC 10），或透過觀星確定位置（DC 15）",
    ),
    Tool.POISONER_KIT: ToolInfo(
        ability="智力",
        utilize="偵測被下毒的物體（DC 10）",
        craft="基本毒藥",
    ),
    Tool.THIEVES_TOOLS: ToolInfo(
        ability="敏捷",
        utilize="撬鎖（DC 15），或拆卸陷阱（DC 15）",
    ),
    # ── 遊戲組 ──
    Tool.DICE_SET: ToolInfo(
        ability="感知",
        utilize="辨別某人是否在作弊（DC 10），或贏得遊戲（DC 20）",
    ),
    Tool.DRAGONCHESS_SET: ToolInfo(
        ability="感知",
        utilize="辨別某人是否在作弊（DC 10），或贏得遊戲（DC 20）",
    ),
    Tool.PLAYING_CARDS: ToolInfo(
        ability="感知",
        utilize="辨別某人是否在作弊（DC 10），或贏得遊戲（DC 20）",
    ),
    Tool.THREE_DRAGON_ANTE: ToolInfo(
        ability="感知",
        utilize="辨別某人是否在作弊（DC 10），或贏得遊戲（DC 20）",
    ),
    # ── 樂器 ──
    Tool.BAGPIPES: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
    Tool.DRUM: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
    Tool.DULCIMER: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
    Tool.FLUTE: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
    Tool.HORN: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
    Tool.LUTE: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
    Tool.LYRE: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
    Tool.PAN_FLUTE: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
    Tool.SHAWM: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
    Tool.VIOL: ToolInfo(
        ability="魅力",
        utilize="演奏一首已知曲目（DC 10），或即興演奏一首歌（DC 15）",
    ),
}

ABILITY_ZH: dict[Ability, str] = {
    Ability.STR: "力量",
    Ability.DEX: "敏捷",
    Ability.CON: "體質",
    Ability.INT: "智力",
    Ability.WIS: "感知",
    Ability.CHA: "魅力",
}
