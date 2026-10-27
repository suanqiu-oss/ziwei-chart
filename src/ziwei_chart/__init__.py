"""ziwei-chart: deterministic Zi Wei Dou Shu natal chart casting.

>>> from datetime import datetime
>>> from zoneinfo import ZoneInfo
>>> from ziwei_chart import BirthInput, cast_chart
>>> chart = cast_chart(BirthInput(
...     datetime=datetime(2004, 4, 25, 9, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
...     gender="女"))
>>> chart.to_dict()["schema"]
'ziwei_chart.v1'
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from .calendar import CalendarRules, resolve_calendar
from .models import Chart, HoroscopeChart
from .natal import build_natal_chart
from .rules import RuleSet

Gender = Literal["男", "女"]


@dataclass
class BirthInput:
    """Birth data for casting.

    - ``datetime``: aware civil birth datetime with an IANA ZoneInfo.
    - ``gender``: "男" or "女".
    - ``longitude``/``latitude``: optional; when both are given the civil
      time is converted to true solar time (requires the ``[solar]`` extra).
      Place names are resolved by the caller.
    - ``bazi``/``lunar_date_str``: optional precomputed calendar.  When both
      are provided they are used as-is and ``datetime`` may be None — this is
      the path used by applications that keep their own calendar service.
    """

    datetime: datetime | None = None
    gender: Gender = "男"
    longitude: float | None = None
    latitude: float | None = None
    bazi: str | None = None
    lunar_date_str: str | None = None
    calendar_rules: CalendarRules = field(default_factory=CalendarRules)

    def __post_init__(self):
        if self.gender not in ("男", "女"):
            raise ValueError("紫微斗数暂不支持非二元性别")
        has_precomputed = self.bazi is not None or self.lunar_date_str is not None
        if has_precomputed and not (self.bazi and self.lunar_date_str):
            raise ValueError("bazi and lunar_date_str must be provided together")
        if not has_precomputed and self.datetime is None:
            raise ValueError("either datetime or a precomputed bazi/lunar_date_str is required")


def cast_chart(birth_input: BirthInput, rules: RuleSet | None = None) -> Chart:
    """Cast the natal chart (and unlock horoscope views) from a BirthInput."""
    rules = rules or RuleSet.default()
    if birth_input.bazi and birth_input.lunar_date_str:
        chart = cast_chart_from_calendar(
            bazi=birth_input.bazi, lunar_date_str=birth_input.lunar_date_str,
            gender=birth_input.gender, rules=rules,
        )
        if birth_input.datetime is not None:
            chart.input_receipt["datetime"] = birth_input.datetime.isoformat()
        return chart

    calendar_info = resolve_calendar(
        birth_input.datetime, birth_input.longitude, birth_input.latitude,
        birth_input.calendar_rules,
    )
    chart = cast_chart_from_calendar(
        bazi=calendar_info.bazi, lunar_date_str=calendar_info.lunar_date_str,
        gender=birth_input.gender, rules=rules,
    )
    chart.calendar = calendar_info
    chart.input_receipt.update(calendar_info.as_receipt())
    if birth_input.datetime is not None:
        chart.input_receipt["datetime"] = birth_input.datetime.isoformat()
    if birth_input.longitude is not None and birth_input.latitude is not None:
        chart.input_receipt["coordinates"] = [birth_input.latitude, birth_input.longitude]
    return chart


def cast_chart_from_calendar(bazi: str, lunar_date_str: str, gender: str,
                             rules: RuleSet | None = None) -> Chart:
    """Cast the natal chart from a precomputed bazi + lunar_date_str pair."""
    return build_natal_chart(bazi=bazi, lunar_date_str=lunar_date_str,
                             gender=gender, rules=rules)


__all__ = [
    "BirthInput",
    "CalendarRules",
    "Chart",
    "HoroscopeChart",
    "RuleSet",
    "cast_chart",
    "cast_chart_from_calendar",
]
__version__ = "0.1.0"
