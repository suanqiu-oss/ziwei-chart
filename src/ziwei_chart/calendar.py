"""Calendar resolution: true solar time, day/time-switch rules, bazi and
lunar date computation via lunar-python.

Default rules match the legacy suanqiu behaviour exactly:
- ``day_rule="zi-early"``: 23:00 (子初) starts the next day pillar.
- ``time_rule="next-day"``: the hour pillar for 23:00-24:00 is computed at
  00:30 of the following civil day.
- the lunar date used by the chart itself follows civil midnight, NOT the
  day-pillar switch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DayRule = Literal["midnight", "zi-early", "solar-midnight"]
TimeRule = Literal["midnight", "prev-day", "next-day"]


class LunarDateTime(NamedTuple):
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int


_LUNAR_DATETIME_RE = re.compile(r"^\s*(\d{1,4})-(\d{1,2})-(\d{1,2}) (\d{1,2}):(\d{1,2}):(\d{1,2})\s*$")


def parse_lunar_datetime(text: str) -> LunarDateTime:
    """解析 lunar_date_str。农历二月有廿九/三十，不能用 datetime.strptime。"""
    match = _LUNAR_DATETIME_RE.match(text or "")
    if not match:
        raise ValueError(f"Invalid lunar date string: {text!r}")
    value = LunarDateTime(*(int(part) for part in match.groups()))
    if not (1 <= value.month <= 12 and 1 <= value.day <= 30
            and value.hour < 24 and value.minute < 60 and value.second < 60):
        raise ValueError(f"Invalid lunar date string: {text!r}")
    return value


@dataclass(frozen=True)
class CalendarRules:
    day_rule: DayRule = "zi-early"
    time_rule: TimeRule = "next-day"


@dataclass
class CalendarInfo:
    bazi: str
    lunar_date_str: str
    true_solar_time: datetime | None   # from_calendar 路径时为 None
    timezone: str
    day_rule: DayRule
    time_rule: TimeRule
    civil_datetime: datetime | None = None

    def as_receipt(self) -> dict:
        return {
            "bazi": self.bazi,
            "lunar_date_str": self.lunar_date_str,
            "true_solar_time": (
                self.true_solar_time.strftime("%Y-%m-%d %H:%M:%S")
                if self.true_solar_time else None
            ),
            "timezone": self.timezone,
            "calendar_rules": {"day_rule": self.day_rule, "time_rule": self.time_rule},
        }


def apply_day_switch(dt_ast: datetime, ast_hour_float: float, tz: str,
                     day_rule: DayRule = "zi-early") -> datetime:
    """day_rule: "midnight" 子正换日 | "zi-early" 子初换日 | "solar-midnight" 真太阳午夜."""
    dt_ast = dt_ast.astimezone(ZoneInfo(tz))
    if day_rule == "zi-early":
        if 23.0 <= ast_hour_float < 24.0:
            return dt_ast + timedelta(days=1)
    elif day_rule == "solar-midnight":
        if ast_hour_float < 0.5:
            return dt_ast + timedelta(days=1)
    # "midnight" 不动
    return dt_ast


def apply_time_switch(dt_for_day: datetime, ast_hour_float: float, tz: str,
                      time_rule: TimeRule = "next-day") -> datetime:
    """time_rule: "midnight" 民用日界 | "next-day" 夜子归次日 | "prev-day" 早子归前日."""
    dt_for_day = dt_for_day.astimezone(ZoneInfo(tz))
    if time_rule == "next-day" and 23.0 <= ast_hour_float < 24.0:
        # 不要简单 +1 小时（会跨到次次日）；直接把时间“对齐”到当日 00:30
        return dt_for_day.replace(hour=0, minute=30, second=0, microsecond=0)
    if time_rule == "prev-day" and 0.0 <= ast_hour_float < 1.0:
        prev = dt_for_day - timedelta(days=1)
        return prev.replace(hour=23, minute=30, second=0, microsecond=0)
    return dt_for_day


def _timezone_name(dt: datetime) -> str:
    tz_name = getattr(dt.tzinfo, "key", None)
    if not tz_name:
        raise ValueError("BirthInput.datetime must carry an IANA ZoneInfo timezone")
    return tz_name


def resolve_calendar(dt: datetime, longitude: float | None, latitude: float | None,
                     rules: CalendarRules) -> CalendarInfo:
    """Compute bazi + chart lunar date from an aware civil datetime.

    With ``longitude``/``latitude`` the civil time is first converted to true
    solar time (requires the ``[solar]`` extra).  Without them the datetime is
    used as-is — no longitude or DST assumptions.
    """
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("BirthInput.datetime must be timezone-aware")
    tz = _timezone_name(dt)
    if longitude is not None and latitude is not None:
        from .solar_time import resolve_true_solar_time

        dt_ast = resolve_true_solar_time(dt, lat=latitude, lon=longitude, tz=tz)
    else:
        dt_ast = dt.astimezone(ZoneInfo(tz))
    h_ast = dt_ast.hour + dt_ast.minute / 60.0 + dt_ast.second / 3600.0

    from lunar_python import Solar

    dt_for_day = apply_day_switch(dt_ast, h_ast, tz, day_rule=rules.day_rule)
    dt_for_bazi = apply_time_switch(dt_for_day, h_ast, tz, time_rule=rules.time_rule)
    solar_obj = Solar.fromYmdHms(
        dt_for_bazi.year, dt_for_bazi.month, dt_for_bazi.day,
        dt_for_bazi.hour, dt_for_bazi.minute, dt_for_bazi.second,
    )
    ec = solar_obj.getLunar().getEightChar()

    # 紫微使用实际排盘时刻的农历日期，不能继承八字日柱的子初换日。
    chart_lunar = Solar.fromYmdHms(
        dt_ast.year, dt_ast.month, dt_ast.day,
        dt_ast.hour, dt_ast.minute, dt_ast.second,
    ).getLunar()
    lunar_year = chart_lunar.getYear()
    lunar_month = abs(chart_lunar.getMonth())  # leap months come back negative
    lunar_day = chart_lunar.getDay()
    # 农历日期不能塞进公历 datetime：二月廿九/三十在公历二月不存在。只拼字符串。
    lunar_date_str = (
        f"{lunar_year:04d}-{lunar_month:02d}-{lunar_day:02d} "
        f"{dt_ast.hour:02d}:{dt_ast.minute:02d}:{dt_ast.second:02d}"
    )
    return CalendarInfo(
        bazi=f"{ec.getYear()}{ec.getMonth()}{ec.getDay()}{ec.getTime()}",
        lunar_date_str=lunar_date_str,
        true_solar_time=dt_ast,
        timezone=tz,
        day_rule=rules.day_rule,
        time_rule=rules.time_rule,
        civil_datetime=dt,
    )
