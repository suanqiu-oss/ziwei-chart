"""Natal chart assembly: 定命身宫、五行局、安星、起大限.

Ported from suanqiu's ``StarSettingService`` with the global singletons and
working-directory reads removed: rule tables come from a ``RuleSet``.
"""
from __future__ import annotations

from typing import Literal

from .calendar import CalendarInfo, parse_lunar_datetime
from .models import BirthChart, Chart, Palace, Star
from .rules import RuleSet

Gender = Literal["男", "女"]

_BASE_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
_BASE_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

_LONG_PALACES = [
    "命宫", "父母宫", "福德宫", "田宅宫", "官禄宫", "交友宫", "迁移宫", "疾厄宫",
    "财帛宫", "子女宫", "夫妻宫", "兄弟宫",
]
_SHORT_PALACES = ["命宫", "父母", "福德", "田宅", "官禄", "交友", "迁移", "疾厄",
                  "财帛", "子女", "夫妻", "兄弟"]


def _check_input(bazi: str, lunar_date_str: str, gender: str) -> None:
    if not bazi or len(bazi) != 8:
        raise ValueError("输入八字有误")
    if not lunar_date_str:
        raise ValueError("输入真太阳时有误")
    if not gender or gender not in ("男", "女"):
        raise ValueError("紫微斗数暂不支持非二元性别")


def _check_direction(gender: str, birth_stem: str) -> bool:
    # 阳男阴女顺行大运, 阴男阳女逆行大运
    flag1 = 1 if gender == "男" else -1
    flag2 = 1 if birth_stem in ["甲", "丙", "戊", "庚", "壬"] else -1
    return (flag1 * flag2) > 0


def _set_decennial_cycle(birth_chart: BirthChart, birth_year: int,
                         wuxingju_num: int, gender: str, birth_stem: str) -> None:
    # 设置 10 年大运, 年龄, 时间期限
    clockwise = _check_direction(gender, birth_stem)
    i = 0
    start = wuxingju_num
    cycl_list = []  # [(start, end), ...]
    while i < 12:
        cycl_list.append((start, start + 9))
        start += 10
        i += 1

    j = 0
    for palace in birth_chart.palace_list:
        if clockwise:
            palace.decennial_cycl = cycl_list[j]
            j += 1
        else:
            palace.decennial_cycl = cycl_list[(j % 12)]
            j -= 1

        start_year = birth_year + palace.decennial_cycl[0] - 1
        end_year = birth_year + palace.decennial_cycl[1] - 1
        palace.decennial_cycl_year_range = range(start_year, end_year + 1)


def set_12gong(birth_chart: BirthChart, birth_month: int, birth_shichen: int,
               bazi: str, rules: RuleSet) -> None:
    base_branch = set_base_branch(birth_month, birth_shichen)  # 命宫地支
    base_index = _BASE_BRANCHES.index(base_branch)
    yingong_stem = set_yingong_stem(bazi[0], rules)
    if yingong_stem not in _BASE_STEMS:
        raise ValueError(f"寅宫天干 {yingong_stem} 不在预设的十天干列表中，请检查配置。")
    stem_start_index = _BASE_STEMS.index(yingong_stem)

    # 从命宫开始的顺时针顺序
    for i, palace_name in enumerate(_LONG_PALACES):
        # 宫位的地支：从命宫下标 base_index 出发，顺时针 + i
        branch_index = (base_index + i) % 12
        branch = _BASE_BRANCHES[branch_index]

        # distance = (此宫地支Index - 寅的Index) mod 12
        distance = (branch_index - 2) % 12
        stem_index = (stem_start_index + distance) % 10
        stem = _BASE_STEMS[stem_index]

        birth_chart.add_palace(Palace(name=_SHORT_PALACES[i], stem=stem, branch=branch))


def _wuxingju_num(birth_chart: BirthChart, rules: RuleSet) -> int:
    wuxing_config = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
    minggong_ganzhi = birth_chart.palace_list[0].stem + birth_chart.palace_list[0].branch
    nayin = rules.jiazi[minggong_ganzhi]
    return wuxing_config[nayin]


def get_ziwei_location(lunar_day: int, wuxingju_num: int) -> str:
    start_index_config = {6: "酉", 5: "午", 4: "亥", 3: "辰", 2: "丑"}
    branch_list = ["酉", "午", "亥", "辰", "丑"]
    ziweijue_start_index = branch_list.index(start_index_config[wuxingju_num])

    quotient = lunar_day // wuxingju_num   # 商数顺数
    remainder = lunar_day % wuxingju_num   # 余数逆数
    if remainder > 0:
        ziweijue_start_index = (ziweijue_start_index + remainder - 1) % 5
        start_branch_index = _BASE_BRANCHES.index(branch_list[ziweijue_start_index])
    else:
        start_branch_index = _BASE_BRANCHES.index("寅")
        quotient -= 1
    branch_index = (start_branch_index + quotient) % 12
    return _BASE_BRANCHES[branch_index]


def set_base_branch(month: int, time_period: int) -> str:
    """
    根据农历月份与时辰确定命宫宫位。

    :param month: 农历月份 (1 ~ 12)
    :param time_period: 时辰序号 (1 ~ 12)，子时=1，丑时=2，...
    """
    start_index = 2  # 寅
    month_index = (start_index + (month - 1)) % 12
    final_index = (month_index - (time_period - 1)) % 12
    return _BASE_BRANCHES[final_index]


def set_yingong_stem(stem_year: str, rules: RuleSet) -> str:
    """五虎遁：由年干得寅宫宫干。"""
    return rules.wuhu[stem_year]


def _second_level_star_locations(birth_month: int, birth_shichen: int, bazi: str,
                                 rules: RuleSet) -> dict[str, list[Star]]:
    location_map: dict[str, list[Star]] = {branch: [] for branch in _BASE_BRANCHES}
    # 左辅: 从辰开始, 顺时针数月份
    zuofu_location = _BASE_BRANCHES[(_BASE_BRANCHES.index("辰") - 1 + birth_month) % 12]
    # 右弼: 从戌开始, 逆时针数月份
    youbi_location = _BASE_BRANCHES[(_BASE_BRANCHES.index("戌") + 1 - birth_month) % 12]
    # 文曲：从辰宫开始，顺时针数到出生时辰
    wenqu_location = _BASE_BRANCHES[(_BASE_BRANCHES.index("辰") - 1 + birth_shichen) % 12]
    # 文昌：从戌宫开始，逆时针数到出生时辰
    wenchang_location = _BASE_BRANCHES[(_BASE_BRANCHES.index("戌") + 1 - birth_shichen) % 12]
    # 地劫：从亥宫开始，顺时针数到出生时辰
    dijie_location = _BASE_BRANCHES[(_BASE_BRANCHES.index("亥") - 1 + birth_shichen) % 12]
    # 地空：从亥宫开始，逆时针数到出生时辰
    dikong_location = _BASE_BRANCHES[(_BASE_BRANCHES.index("亥") + 1 - birth_shichen) % 12]
    # 禄存: 根据出生年的天干确定禄存星的位置
    lucun_dict = {
        "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
        "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
    }
    lucun_location = lucun_dict[bazi[0]]
    # 擎羊：禄存前一位
    qingyang_location = _BASE_BRANCHES[(_BASE_BRANCHES.index(lucun_location) + 1) % 12]
    # 陀罗：禄存后一位
    tuoluo_location = _BASE_BRANCHES[(_BASE_BRANCHES.index(lucun_location) - 1) % 12]
    # 天魁天钺: 甲戊庚之年丑未，乙己之年子申，辛年午寅，壬癸之年卯巳，丙丁之年亥酉。
    tiankui_dict = {
        "甲": "丑", "戊": "丑", "庚": "丑", "乙": "子", "己": "子",
        "辛": "午", "壬": "卯", "癸": "卯", "丙": "亥", "丁": "亥",
    }
    tianyue_dict = {
        "甲": "未", "戊": "未", "庚": "未", "乙": "申", "己": "申",
        "辛": "寅", "壬": "巳", "癸": "巳", "丙": "酉", "丁": "酉",
    }
    tiankui_location = tiankui_dict[bazi[0]]
    tianyue_location = tianyue_dict[bazi[0]]
    # 火星铃星: 申子辰人寅戌扬，寅午戌人丑卯方；巳酉丑人卯戌位，亥卯未人酉戌房。
    huoxing_start_dict = {
        "申": "寅", "子": "寅", "辰": "寅", "寅": "丑", "午": "丑", "戌": "丑",
        "巳": "卯", "酉": "卯", "丑": "卯", "亥": "酉", "卯": "酉", "未": "酉",
    }
    lingxing_start_dict = {
        "申": "戌", "子": "戌", "辰": "戌", "寅": "卯", "午": "卯", "戌": "卯",
        "巳": "戌", "酉": "戌", "丑": "戌", "亥": "戌", "卯": "戌", "未": "戌",
    }
    huoxing_location = _BASE_BRANCHES[
        (_BASE_BRANCHES.index(huoxing_start_dict[bazi[1]]) - 1 + birth_shichen) % 12]
    lingxing_location = _BASE_BRANCHES[
        (_BASE_BRANCHES.index(lingxing_start_dict[bazi[1]]) - 1 + birth_shichen) % 12]
    # 天马: 寅午戌马在申，卯未亥马在巳，申子辰马在寅，巳酉丑马在亥。
    tianma_dict = {
        "寅": "申", "午": "申", "戌": "申", "卯": "巳", "未": "巳", "亥": "巳",
        "申": "寅", "子": "寅", "辰": "寅", "巳": "亥", "酉": "亥", "丑": "亥",
    }
    tianma_location = tianma_dict[bazi[1]]

    for location, name in [
        (zuofu_location, "左辅"), (youbi_location, "右弼"),
        (wenqu_location, "文曲"), (wenchang_location, "文昌"),
        (dijie_location, "地劫"), (dikong_location, "地空"),
        (lucun_location, "禄存"), (qingyang_location, "擎羊"),
        (tuoluo_location, "陀罗"), (tiankui_location, "天魁"),
        (tianyue_location, "天钺"), (huoxing_location, "火星"),
        (lingxing_location, "铃星"), (tianma_location, "天马"),
    ]:
        location_map[location].append(Star(name=name, level="乙", rules=rules))
    return location_map


def build_natal_chart(bazi: str, lunar_date_str: str, gender: str,
                      rules: RuleSet | None = None) -> Chart:
    """Assemble the natal chart from a precomputed calendar (bazi + lunar date)."""
    rules = rules or RuleSet.default()
    _check_input(bazi, lunar_date_str, gender)

    birth_stem = bazi[0]
    lunar_datetime = parse_lunar_datetime(lunar_date_str)

    birth_chart = BirthChart()
    birth_month = lunar_datetime.month
    shichen_index = _BASE_BRANCHES.index(bazi[7])
    birth_shichen = shichen_index + 1

    set_12gong(birth_chart, birth_month, birth_shichen, bazi, rules)
    ju_num = _wuxingju_num(birth_chart, rules)
    _set_decennial_cycle(birth_chart, lunar_datetime.year, ju_num, gender, birth_stem)
    birth_chart.set_decennial_index()
    _set_stars(birth_chart, bazi, birth_month, birth_shichen, birth_stem, lunar_datetime, rules)
    birth_chart.set_3fang4zheng()

    calendar_info = CalendarInfo(
        bazi=bazi, lunar_date_str=lunar_date_str,
        true_solar_time=None, timezone="",
        day_rule="midnight", time_rule="midnight",
    )
    input_receipt = {
        "bazi": bazi,
        "lunar_date_str": lunar_date_str,
        "gender": gender,
        "datetime": None,  # 调用方走 from_calendar 路径时不回填民用时刻
    }
    return Chart(birth_chart, calendar_info, birth_month, birth_shichen, gender,
                 rules, input_receipt)


def _set_stars(birth_chart: BirthChart, bazi: str, birth_month: int, birth_shichen: int,
               birth_stem: str, lunar_datetime, rules: RuleSet) -> None:
    _set_main_stars(birth_chart, bazi, birth_stem, lunar_datetime, rules)
    _set_second_level_star(birth_chart, birth_month, birth_shichen, bazi, rules)
    _set_birth_sihua(birth_chart, birth_stem, rules)


def _set_main_stars(birth_chart: BirthChart, bazi: str, birth_stem: str,
                    lunar_datetime, rules: RuleSet) -> None:
    ziwei_branch = get_ziwei_location(lunar_datetime.day,
                                      _wuxingju_num(birth_chart, rules))
    key = f"紫微在{ziwei_branch}"
    base_chart = rules.mainstar[key]

    for palace in birth_chart.palace_list:
        star_names = base_chart.get(palace.branch)
        for star_name in star_names:
            star = Star(name=star_name, birth_stem=birth_stem,
                        palace_stem=palace.stem, palace=palace.name,
                        level="甲", rules=rules)
            star.set_time_type("本命")
            palace.add_star(star)


def _set_second_level_star(birth_chart: BirthChart, birth_month: int, birth_shichen: int,
                           bazi: str, rules: RuleSet) -> None:
    location_map = _second_level_star_locations(birth_month, birth_shichen, bazi, rules)
    for palace in birth_chart.palace_list:
        for star in location_map.get(palace.branch, []):
            star.set_palace(palace.name)
            star.set_time_type("本命")
            palace.add_star(star)


def _set_birth_sihua(birth_chart: BirthChart, birth_stem: str, rules: RuleSet) -> None:
    for palace in birth_chart.palace_list:
        for star in palace.original:
            star.transformation = rules.sihua.get_transformation(birth_stem, star.name)
