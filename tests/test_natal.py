"""Natal chart tests ported from suanqiu's test_star_setting_service /
test_lunar_date_str."""
from __future__ import annotations

import pytest

from ziwei_chart import BirthInput, cast_chart_from_calendar
from ziwei_chart.calendar import parse_lunar_datetime


def chart_for(bazi: str, lunar_date_str: str, gender: str = "男"):
    return cast_chart_from_calendar(bazi=bazi, lunar_date_str=lunar_date_str, gender=gender)


def test_exact_division_places_ziwei_in_you_and_tianji_taiyin_in_shen():
    # 1998-02-20 11:30 is lunar 1998-01-24, an 午 hour.
    # 戊寅年 gives 庚申命宫 (木三局), so day 24 is exactly divisible by 3.
    chart = chart_for(bazi="戊寅甲寅戊戌戊午", lunar_date_str="1998-01-24 11:30:00")

    assert chart.birth_chart.palace_list[0].branch == "申"
    shen_palace = next(p for p in chart.birth_chart.palace_list if p.branch == "申")
    main_stars = {star.name for star in shen_palace.original if star.level == "甲"}
    assert main_stars == {"天机", "太阴"}


def test_palace_stems_follow_wuhu_and_palace_sequence():
    chart = chart_for(bazi="甲申戊辰甲戌己巳", lunar_date_str="2004-03-07 09:20:00", gender="女")
    ming = chart.birth_chart.palace_list[0]
    # 甲年五虎遁 -> 丙寅起宫干；农历三月巳时 -> 命宫在亥，乙亥
    assert ming.branch == "亥"
    assert ming.stem == "乙"
    assert [p.name for p in chart.birth_chart.palace_list[:3]] == ["命宫", "父母", "福德"]


def test_parse_lunar_datetime_accepts_unpadded_and_rejects_garbage():
    assert parse_lunar_datetime("2004-3-7 09:20:00") == (2004, 3, 7, 9, 20, 0)
    with pytest.raises(ValueError):
        parse_lunar_datetime("1990-08-31 00:00:00")
    with pytest.raises(ValueError):
        parse_lunar_datetime("demo lunar date")


def test_lunar_dates_missing_from_gregorian_february_are_accepted():
    # 二月三十 / 二月廿九 不能经过公历 datetime
    for lunar_date_str, expected_day in [("1981-02-30 10:00:00", 30),
                                         ("1982-02-29 10:00:00", 29)]:
        chart = chart_for(bazi="辛酉壬辰甲子己巳",
                          lunar_date_str=lunar_date_str, gender="女")
        assert chart.birth_month == 2
        assert chart.birth_chart.palace_list  # 盘正常生成


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError, match="八字"):
        cast_chart_from_calendar(bazi="甲子", lunar_date_str="2004-03-07 09:00:00", gender="男")
    with pytest.raises(ValueError, match="性别"):
        cast_chart_from_calendar(bazi="甲申戊辰甲戌己巳",
                                 lunar_date_str="2004-03-07 09:00:00", gender="其他")


def test_birth_input_validation():
    with pytest.raises(ValueError, match="性别"):
        BirthInput(gender="其他", bazi="甲", lunar_date_str="x")
    with pytest.raises(ValueError, match="together"):
        BirthInput(gender="男", bazi="甲")
    with pytest.raises(ValueError, match="required"):
        BirthInput(gender="男")


def test_horoscope_does_not_mutate_natal():
    import copy

    chart = chart_for(bazi="甲申戊辰甲戌己巳", lunar_date_str="2004-03-07 09:20:00", gender="女")
    before = copy.deepcopy(chart.to_dict())
    chart.horoscope(year=2026)
    chart.horoscope(year=2025, month=6, is_leap=True)  # 2025 才有闰六月
    assert chart.to_dict() == before
