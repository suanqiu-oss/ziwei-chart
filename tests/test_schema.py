"""Every public output must validate against the bundled v1 JSON Schema."""
from __future__ import annotations

import json
from datetime import datetime
from importlib import resources
from zoneinfo import ZoneInfo

import pytest

jsonschema = pytest.importorskip("jsonschema")

from ziwei_chart import BirthInput, RuleSet, cast_chart  # noqa: E402

SCHEMA = json.loads(
    resources.files("ziwei_chart").joinpath("schema/ziwei_chart.v1.json").read_text("utf-8")
)


def _chart():
    return cast_chart(BirthInput(
        datetime=datetime(2004, 4, 25, 9, 20, tzinfo=ZoneInfo("Asia/Shanghai")), gender="女"))


@pytest.mark.parametrize("view", ["natal", "yearly", "monthly", "decennial"])
def test_outputs_validate(view):
    chart = _chart()
    payload = {
        "natal": lambda: chart.to_dict(),
        "yearly": lambda: chart.horoscope(year=2026).to_dict(),
        "monthly": lambda: chart.horoscope(year=2025, month=6, is_leap=True).to_dict(),
        "decennial": lambda: chart.horoscope(age=30).to_dict(),
    }[view]()
    jsonschema.validate(payload, SCHEMA)
    assert payload["schema"] == "ziwei_chart.v1"
    assert payload["input"]["bazi"] == chart.input_receipt["bazi"]
    assert ("horoscope" in payload) == (view != "natal")


def test_horoscope_metadata_carries_decennial_ranges():
    chart = _chart()
    meta = chart.horoscope(year=2026).to_dict()["horoscope"]
    assert meta["mode"] == "yearly"
    start, end = (int(part) for part in meta["year_range"].split("-"))
    assert start <= 2026 <= end and end - start == 9
    age_start, age_end = (int(part) for part in meta["age_range"].split("-"))
    assert age_end - age_start == 9
    assert meta["monthly"] is None

    monthly = chart.horoscope(year=2025, month=6, is_leap=True).to_dict()["horoscope"]
    assert monthly["mode"] == "monthly"
    assert monthly["monthly"]["label"] == "闰六月"


def test_default_rules_are_loaded_once():
    assert RuleSet.default() is RuleSet.default()
