"""Custom rule injection (流派差异) must change the output, not the core."""
from __future__ import annotations

from ziwei_chart import RuleSet, cast_chart_from_calendar


def _chart(rules):
    return cast_chart_from_calendar(bazi="庚辰乙酉甲午壬申",
                                    lunar_date_str="2000-09-06 15:20:00",
                                    gender="男", rules=rules)


def test_default_rules_produce_default_transformations():
    chart = _chart(RuleSet.default())
    stars = {s["name"]: s["transformation"] for p in chart.to_dict()["palaces"]
             for s in p["original"]}
    assert stars["太阳"] == "禄"
    assert stars["武曲"] == "权"


def test_custom_sihua_changes_output():
    default = _chart(RuleSet.default())
    custom_table = {
        stem: dict(stars) for stem, stars in _read_default_sihua().items()
    }
    # 庚干换派：科曜由太阴改为天相
    custom_table["庚"] = {"太阳": "禄", "武曲": "权", "天相": "科", "天同": "忌"}
    custom = _chart(RuleSet.default().with_sihua(custom_table))
    assert custom.to_dict() != default.to_dict()
    transformed = [s["name"] for p in custom.to_dict()["palaces"]
                   for s in p["original"] if s["transformation"]]
    assert "天相" in transformed


def _read_default_sihua() -> dict:
    import json
    from importlib import resources

    text = resources.files("ziwei_chart").joinpath("data/sihua_config.json").read_text("utf-8")
    return json.loads(text)
