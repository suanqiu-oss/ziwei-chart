"""Rule tables: 四化, 五虎遁, 60 甲子纳音, 十四主星安星表.

Tables ship as package data and are loaded once via ``importlib.resources``
— no working-directory or global-singleton dependency.  A different 四化表
(school disagreement, e.g. 庚干) can be injected through ``rules=``.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Mapping

_STEMS = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")


class SihuaTable:
    """生年四化表：天干 -> 星曜 -> 禄权科忌."""

    def __init__(self, config: Mapping[str, Mapping[str, str]]):
        self._config = {stem: dict(stars) for stem, stars in config.items()}

    def get_transformation(self, stem: str | None, star_name: str) -> str:
        if not stem:
            return ""
        if stem not in _STEMS:
            raise ValueError(f"输入天干错误, {stem}")
        return self._config.get(stem, {}).get(star_name, "")

    @classmethod
    def from_dict(cls, config: Mapping[str, Mapping[str, str]]) -> "SihuaTable":
        return cls(config)


class RuleSet:
    """Immutable bundle of the four rule tables used while casting."""

    def __init__(self, sihua: SihuaTable, wuhu: Mapping[str, str],
                 jiazi: Mapping[str, str], mainstar: Mapping[str, Mapping[str, list[str]]]):
        self.sihua = sihua
        self.wuhu = dict(wuhu)
        self.jiazi = dict(jiazi)
        self.mainstar = {key: dict(value) for key, value in mainstar.items()}

    @classmethod
    def default(cls) -> "RuleSet":
        """The bundled tables, read once per process and shared across casts.

        Treat the returned object as read-only; use ``with_sihua`` for a variant.
        """
        return _default_ruleset()

    def with_sihua(self, config: Mapping[str, Mapping[str, str]]) -> "RuleSet":
        """Return a copy whose 四化表 is replaced (流派差异注入点)."""
        return RuleSet(SihuaTable(config), self.wuhu, self.jiazi, self.mainstar)


@lru_cache(maxsize=1)
def _default_ruleset() -> RuleSet:
    return RuleSet(
        sihua=SihuaTable(_load_json("sihua_config.json")),
        wuhu=_load_json("wuhu_config.json"),
        jiazi=_load_json("60jiazi.json"),
        mainstar=_load_json("6base_mainstar_location.json"),
    )


def _load_json(name: str) -> dict:
    text = resources.files("ziwei_chart").joinpath(f"data/{name}").read_text(encoding="utf-8")
    return json.loads(text)
