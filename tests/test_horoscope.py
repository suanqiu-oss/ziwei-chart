"""Horoscope layer tests ported from suanqiu's test_ziwei_monthly (service
level) and test_decennial_ranges."""
from __future__ import annotations

import pytest

from ziwei_chart import cast_chart_from_calendar
from ziwei_chart.horoscope import lunar_months


def chart_for():
    return cast_chart_from_calendar(bazi="甲申戊辰甲戌己巳",
                                    lunar_date_str="2004-03-07 09:20:00", gender="女")


def test_calendar_and_leap_month():
    normal = lunar_months(2026)
    assert len(normal) == 12
    assert normal[0] == dict(month=1, is_leap=False, stem="庚", branch="寅", label="正月",
                             start_date="2026-02-17", end_date="2026-03-18")
    leap = [m for m in lunar_months(2025) if m["month"] == 6]
    assert [m["label"] for m in leap] == ["六月", "闰六月"]
    assert [(m["stem"], m["branch"]) for m in leap] == [("癸", "未"), ("癸", "未")]
    normal[0]["month"] = 12
    assert lunar_months(2026)[0]["month"] == 1


def test_doujun_inclusive_counting_and_next_month():
    chart = chart_for()
    view = _monthly(chart, 2026, 1, False, birth_month=3, birth_shichen=5)
    assert view.monthly["doujun"] == view.monthly["ming_branch"] == "申"  # March, 辰时
    view2 = _monthly(chart, 2026, 2, False, birth_month=3, birth_shichen=5)
    assert view2.monthly["ming_branch"] == "酉"


def _monthly(chart, year, month, is_leap, birth_month, birth_shichen):
    from ziwei_chart.horoscope import apply_decennial, apply_month, apply_year
    from copy import deepcopy

    copied = deepcopy(chart.birth_chart)
    apply_decennial(copied, year=year)
    apply_year(copied, year=year, rules=chart.rules)
    meta = apply_month(copied, year=year, month=month, is_leap=is_leap,
                       birth_month=birth_month, birth_shichen=birth_shichen,
                       rules=chart.rules)
    from ziwei_chart.models import HoroscopeChart
    return HoroscopeChart(copied, "monthly", year, month, is_leap, meta)


def test_month_layers_are_independent_of_natal():
    chart = chart_for()
    natal = chart.to_dict()
    view = chart.horoscope(year=2026, month=1, is_leap=False)
    assert chart.to_dict() == natal
    monthly_names = [p["month_name"] for p in view.to_dict()["palaces"]]
    assert sum(name == "月命" for name in monthly_names) == 1
    assert all(not p["month_name"] for p in natal["palaces"])


def test_leap_month_repeats_palaces_and_four_transforms():
    chart = chart_for()
    regular = chart.horoscope(year=2025, month=6, is_leap=False).to_dict()
    leap = chart.horoscope(year=2025, month=6, is_leap=True).to_dict()
    assert regular["palaces"] == leap["palaces"]
    assert chart.horoscope(year=2025, month=6, is_leap=True).monthly["label"] == "闰六月"


def test_invalid_month_raises_and_natal_stays_clean():
    chart = chart_for()
    natal = chart.to_dict()
    with pytest.raises(ValueError, match="不存在"):
        chart.horoscope(year=2026, month=6, is_leap=True)
    assert chart.to_dict() == natal


def test_decennial_age_index_includes_cycle_end_age():
    chart = chart_for()
    entries = chart.to_dict()["decennial_age_index"]
    assert entries, "natal chart must carry decennial ranges"
    first = entries[0]
    assert first["end"] == first["start"] + 9
    # v1 输出不再使用 range 字符串键
    assert isinstance(entries, list)


def test_horoscope_year_layers_stacked():
    chart = chart_for()
    view = chart.horoscope(year=2026)
    palaces = view.to_dict()["palaces"]
    assert sum(p["decennial_name"] == "大命" for p in palaces) == 1
    assert sum(p["year_name"] == "流命" for p in palaces) == 1
    # 2026 丙午年：太阳化禄（丙: 天同禄 天机权 文昌科 廉贞忌 —— 太阳无四化）
    # 改断：流年四化字段存在且非空星数 == 4
    transformed = [s for p in palaces for s in p["original"] if s["year_transformation"]]
    assert len(transformed) == 4
