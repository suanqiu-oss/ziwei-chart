"""Golden snapshot tests against the pre-split suanqiu behaviour.

Chart cases compare through the documented v1 field changes:
- drop ``schema`` / ``input`` / ``horoscope``,
- re-stringify decennial index lists into legacy range keys,
- ``Star.property`` and ``Palace.palace_implication`` (interpretation texts,
  owned by the application) are absent on both sides.

Two fixture sets, both exported by suanqiu's ``scripts/export_chart_golden.py``:
- ``golden_ziwei_charts.json``: curated boundary cases stored as whole JSON;
- ``golden_ziwei_digests.json``: 150 seeded random births, stored as sha256
  of the canonical legacy-shape JSON to keep the repository small.

Calendar cases run the datetime path end-to-end; coordinate cases need the
``[solar]`` extra and a DE421 ephemeris.  Set ``ZIWEI_CHART_REQUIRE_SOLAR=1``
(CI does) to make a missing ephemeris fail instead of skip.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ziwei_chart import BirthInput, CalendarRules, cast_chart, cast_chart_from_calendar

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"


def _ephemeris_available() -> bool:
    try:
        import skyfield  # noqa: F401
    except ImportError:
        return False
    candidate = os.environ.get("ZIWEI_CHART_EPHEMERIS")
    if candidate and Path(candidate).is_file():
        return True
    return (Path.home() / ".cache" / "ziwei-chart" / "de421.bsp").is_file()


def require_solar() -> None:
    if _ephemeris_available():
        return
    if os.environ.get("ZIWEI_CHART_REQUIRE_SOLAR") == "1":
        pytest.fail("ZIWEI_CHART_REQUIRE_SOLAR=1 but no skyfield/DE421 ephemeris is available")
    pytest.skip("[solar] ephemeris not available")


def legacy_key(entry: dict) -> tuple[str, dict]:
    key = f"{entry['start']}-{entry['end']}"
    value = {"palace_index": entry["palace_index"],
             "palace_name": entry["palace_name"], "stem": entry["stem"]}
    return key, value


def to_legacy_shape(payload: dict) -> dict:
    payload = {k: v for k, v in payload.items() if k not in ("schema", "input", "horoscope")}
    for field_name in ("decennial_age_index", "decennial_year_index"):
        payload[field_name] = dict(legacy_key(entry) for entry in payload[field_name])
    return payload


def digest(payload: dict) -> str:
    canonical = json.dumps(to_legacy_shape(payload), ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def birth_input(args: dict, gender: str) -> BirthInput:
    coords = args["coords"]
    dt = datetime(args["year"], args["month"], args["day"], args["hour"],
                  args["minute"], args["second"],
                  tzinfo=ZoneInfo(coords[2] if coords else "Etc/GMT-8"))
    return BirthInput(datetime=dt, gender=gender,
                      longitude=coords[1] if coords else None,
                      latitude=coords[0] if coords else None,
                      calendar_rules=CalendarRules())


def _load(name: str) -> list[dict]:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))["cases"]


CHART_CASES = _load("golden_ziwei_charts.json")
CALENDAR_CASES = _load("golden_ziwei_calendar.json")
DIGEST_CASES = _load("golden_ziwei_digests.json")


@pytest.mark.parametrize("case", CHART_CASES, ids=[c["id"] for c in CHART_CASES])
def test_natal_matches_golden(case):
    chart = cast_chart_from_calendar(bazi=case["input"]["bazi"],
                                     lunar_date_str=case["input"]["lunar_date_str"],
                                     gender=case["input"]["gender"])
    assert to_legacy_shape(chart.to_dict()) == case["natal"]


@pytest.mark.parametrize("case", CHART_CASES, ids=[c["id"] for c in CHART_CASES])
def test_horoscopes_match_golden(case):
    chart = cast_chart_from_calendar(bazi=case["input"]["bazi"],
                                     lunar_date_str=case["input"]["lunar_date_str"],
                                     gender=case["input"]["gender"])
    for expected in case["horoscopes"]:
        if expected["kind"] == "yearly":
            view = chart.horoscope(year=expected["year"])
        else:
            view = chart.horoscope(year=expected["year"], month=expected["month"],
                                   is_leap=expected["is_leap"])
            assert view.monthly == expected["meta"]
        assert to_legacy_shape(view.to_dict()) == expected["dict"]


@pytest.mark.parametrize("case", CALENDAR_CASES, ids=[c["id"] for c in CALENDAR_CASES])
def test_calendar_matches_golden(case):
    if case["args"]["coords"]:
        require_solar()
    chart = cast_chart(birth_input(case["args"], "男"))
    got = chart.input_receipt
    expected = case["expected"]
    assert got["bazi"] == expected["bazi"]
    assert got["lunar_date_str"] == expected["lunar_date_str"]
    if case["args"]["coords"]:
        assert got["true_solar_time"] == expected["true_solar_time"]
        assert got["coordinates"] == case["args"]["coords"][:2]


@pytest.mark.parametrize("case", DIGEST_CASES, ids=[c["id"] for c in DIGEST_CASES])
def test_random_births_match_digests(case):
    calendar = case["calendar"]
    chart = cast_chart_from_calendar(bazi=calendar["bazi"],
                                     lunar_date_str=calendar["lunar_date_str"],
                                     gender=case["gender"])
    assert digest(chart.to_dict()) == case["natal_sha256"]
    for view in case["views"]:
        if view["kind"] == "yearly":
            got = chart.horoscope(year=view["year"])
        else:
            got = chart.horoscope(year=view["year"], month=view["month"],
                                  is_leap=view["is_leap"])
            assert got.monthly == view["meta"]
        assert digest(got.to_dict()) == view["sha256"], view


@pytest.mark.parametrize("case", DIGEST_CASES, ids=[c["id"] for c in DIGEST_CASES])
def test_random_births_calendar(case):
    if case["args"]["coords"]:
        require_solar()
    receipt = cast_chart(birth_input(case["args"], case["gender"])).input_receipt
    assert receipt["bazi"] == case["calendar"]["bazi"]
    assert receipt["lunar_date_str"] == case["calendar"]["lunar_date_str"]
    assert receipt["true_solar_time"] == case["calendar"]["true_solar_time"]


def test_full_cast_chart_path_agrees_with_precomputed_path():
    """datetime 排盘与 bazi/lunar 直排必须给出同一张盘（无出生地用例）。"""
    case = next(c for c in CHART_CASES if c["calendar_args"]["coords"] is None)
    from_datetime = cast_chart(birth_input(case["calendar_args"], case["input"]["gender"]))
    from_calendar = cast_chart_from_calendar(bazi=case["input"]["bazi"],
                                             lunar_date_str=case["input"]["lunar_date_str"],
                                             gender=case["input"]["gender"])
    assert to_legacy_shape(from_datetime.to_dict()) == to_legacy_shape(from_calendar.to_dict())
