"""Horoscope layers: 大限 (decennial), 流年 (yearly), 流月 (monthly).

Ported from suanqiu's ``DecennialPalaceSettingService`` and
``ziwei_monthly.set_month_palaces``.  All layers mutate the chart copy they
are given — ``Chart.horoscope`` always passes a deepcopy of the natal chart.
"""
from __future__ import annotations

from functools import lru_cache

from lunar_python import LunarYear, Solar

from .models import BirthChart
from .rules import RuleSet

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"
MONTH_NAMES = ("正月", "二月", "三月", "四月", "五月", "六月",
               "七月", "八月", "九月", "十月", "冬月", "腊月")


def _find_decennial_palace(birth_chart: BirthChart, age: int | None, year: int | None):
    """
    :return: (palace, shift) shift: 大运命宫和本命命宫的偏离
    """
    if year:
        for year_range, tup in birth_chart.decennial_year_index.items():
            if year in year_range:
                return tup
    if age:
        for age_range, tup in birth_chart.decennial_age_index.items():
            if age in age_range:
                return tup
    return None, None


def apply_decennial(birth_chart: BirthChart, year: int | None = None,
                    age: int | None = None) -> dict:
    """叠加流年层之上的大限层：宫名前缀 + 大运四化."""
    main_palace, shift = _find_decennial_palace(birth_chart, age, year)

    if not isinstance(shift, int):
        raise ValueError(f"排大运盘失败, 年龄:{age}, 年份:{year}")
    if not hasattr(main_palace, "stem"):
        raise ValueError(f"排大运盘失败, 年龄:{age}, 年份:{year}")

    short_palaces = ["命", "父", "福", "田", "官", "友", "迁", "疾", "财", "子", "夫", "兄"]
    j = 0
    for palace in birth_chart.palace_list:
        palace.decennial_name = "大" + short_palaces[(j - shift) % 12]
        for star in palace.original:
            star.decennial_transformation = star.set_transformation(main_palace.stem)
        j += 1
    return {
        "age_range": f"{main_palace.decennial_cycl[0]}-{main_palace.decennial_cycl[1]}",
        "year_range": (
            f"{main_palace.decennial_cycl_year_range.start}-"
            f"{main_palace.decennial_cycl_year_range.stop - 1}"
        ),
    }


def apply_year(birth_chart: BirthChart, year: int, rules: RuleSet) -> None:
    """叠加流年层：流年四化 + 流年十二宫标注。须先有对应大限。"""
    main_palace, _ = _find_decennial_palace(birth_chart, age=None, year=year)
    if not hasattr(main_palace, "stem"):
        raise ValueError(f"排流年盘失败, 年份:{year} 不在任何大运范围内")

    ly = LunarYear.fromYear(year)
    year_gan = ly.getGan()
    year_zhi = ly.getZhi()
    year_shift = None
    for index, palace in enumerate(birth_chart.palace_list):
        if palace.branch == year_zhi:
            year_shift = index
            break
    if year_shift is None:
        raise ValueError(f"排流年盘失败, 年份:{year} 的地支 {year_zhi} 未匹配到宫位")

    short_palaces = ["命", "父", "福", "田", "官", "友", "迁", "疾", "财", "子", "夫", "兄"]
    j = 0
    for palace in birth_chart.palace_list:
        palace.year_name = "流" + short_palaces[(j - year_shift) % 12]
        for star in palace.original:
            star.year_transformation = star.set_transformation(year_gan)
        j += 1


@lru_cache(maxsize=256)
def _months(year: int) -> tuple:
    if not 1 <= year <= 9998:
        raise ValueError("年份须在 1–9998 之间")
    stem = STEMS.index(LunarYear.fromYear(year).getGan())
    return tuple(
        (
            abs(item.getMonth()), item.getMonth() < 0,
            STEMS[((stem % 5) * 2 + 2 + abs(item.getMonth()) - 1) % 10],
            BRANCHES[(abs(item.getMonth()) + 1) % 12],
            Solar.fromJulianDay(item.getFirstJulianDay()).toYmd(),
            Solar.fromJulianDay(item.getFirstJulianDay() + item.getDayCount() - 1).toYmd(),
        )
        for item in LunarYear.fromYear(year).getMonths()
        if item.getYear() == year
    )


def lunar_months(year: int) -> list[dict]:
    """Return fresh dictionaries so callers cannot mutate cached calendar data."""
    return [dict(month=month, is_leap=leap, stem=stem, branch=branch,
                 label=("闰" if leap else "") + MONTH_NAMES[month - 1],
                 start_date=start, end_date=end)
            for month, leap, stem, branch, start, end in _months(year)]


def apply_month(birth_chart: BirthChart, *, year: int, month: int, is_leap: bool,
                birth_month: int, birth_shichen: int, rules: RuleSet) -> dict:
    """叠加流月层：斗君起月、五虎遁月干，闰月重复同序月。返回流月元数据。"""
    if not 1 <= birth_month <= 12 or not 1 <= birth_shichen <= 12:
        raise ValueError("出生月份或时辰无效")
    selected = next((item for item in lunar_months(year)
                     if item["month"] == month and item["is_leap"] == is_leap), None)
    if selected is None:
        raise ValueError(f"{year} 年不存在所选农历月份")
    year_branch = BRANCHES.index(LunarYear.fromYear(year).getZhi())
    doujun = (year_branch - (birth_month - 1) + birth_shichen - 1) % 12
    ming = BRANCHES[(doujun + month - 1) % 12]
    shift = next(i for i, palace in enumerate(birth_chart.palace_list)
                 if palace.branch == ming)
    roles = ("命", "父", "福", "田", "官", "友", "迁", "疾", "财", "子", "夫", "兄")
    for i, palace in enumerate(birth_chart.palace_list):
        palace.month_name = "月" + roles[(i - shift) % 12]
        for star in palace.original:
            star.month_transformation = star.set_transformation(selected["stem"])
    return {**selected, "doujun": BRANCHES[doujun], "ming_branch": ming}
