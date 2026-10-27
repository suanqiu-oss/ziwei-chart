"""Core chart models: Star, Palace, BirthChart, Chart.

Deliberate v1 differences from the legacy suanqiu entities:
- ``Star.property`` and ``Palace.palace_implication`` (interpretation text)
  are gone; the calling application re-attaches its own texts.
- ``decennial_age_index`` / ``decennial_year_index`` serialize as a list of
  ``{start, end, palace_index, ...}`` instead of stringified range keys.
- No pandas, no CSV reads, no global state.
"""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, List

from .rules import RuleSet

if TYPE_CHECKING:  # pragma: no cover
    from .natal import CalendarInfo


class Star:
    def __init__(self, name: str, rules: RuleSet, birth_stem: str = "",
                 palace_stem: str = "", palace: str = "", level: str = "",
                 branch: str = ""):
        self.name = name          # 星曜名称
        self.level = level
        self.palace = palace      # 命/财/官 等宫
        self.branch = branch      # 地支
        self.time_type = ""       # 本命/大运/流年/流月
        self._rules = rules

        self.transformation = self.set_transformation(birth_stem)      # 生年四化
        self.self_transformation = self.set_transformation(palace_stem)  # 宫干自化
        self.decennial_transformation = ""   # 大运四化
        self.year_transformation = ""        # 流年四化
        self.month_transformation = ""       # 流月四化

    def set_transformation(self, stem: str | None) -> str:
        return self._rules.sihua.get_transformation(stem, self.name)

    def get_self_transformations(self) -> str:
        if self.self_transformation:
            return f"({self.name}自化{self.self_transformation})"
        return ""

    def set_time_type(self, time_type: str) -> None:
        self.time_type = time_type

    def set_palace(self, palace: str) -> None:
        self.palace = palace

    def __str__(self) -> str:
        string = self.name
        if self.transformation:
            string += f"化{self.transformation}"
        if self.decennial_transformation:
            string += f"(大运化{self.decennial_transformation})"
        if self.year_transformation:
            string += f"(流年化{self.year_transformation})"
        if self.month_transformation:
            string += f"(流月化{self.month_transformation})"
        return string

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "level": self.level,
            "palace": self.palace,
            "branch": self.branch,
            "time_type": self.time_type,
            "transformation": self.transformation,                    # 生年四化
            "self_transformation": self.self_transformation,          # 宫干自化
            "decennial_transformation": self.decennial_transformation,  # 大运四化
            "year_transformation": self.year_transformation,          # 流年四化
            "month_transformation": self.month_transformation,        # 流月四化
        }


class Palace:
    def __init__(self, stem: str = "", branch: str = "", name: str = ""):
        self.stem = stem          # 天干
        self.branch = branch      # 地支
        self.name = name          # 命宫/兄弟宫/...
        self.decennial_name = ""  # 大运宫名
        self.year_name = ""       # 流年宫名
        self.month_name = ""      # 流月宫名
        self.original: List[Star] = []      # 本命盘星曜
        self._3fang_list: List[Star] = []
        self._opposite_list: List[Star] = []
        self.decennial_cycl: tuple = ()
        self.decennial_cycl_year_range: range = range(0)

    def add_star(self, star: Star) -> None:
        self.original.append(star)

    def contain_main_star(self) -> bool:
        return any(star.level == "甲" for star in self.original)

    def get_3fang_branch(self) -> list[str]:
        sanfang_config = {
            "子": ["申", "辰"], "丑": ["巳", "酉"], "寅": ["午", "戌"],
            "卯": ["未", "亥"], "辰": ["申", "子"], "巳": ["酉", "丑"],
            "午": ["寅", "戌"], "未": ["卯", "亥"], "申": ["子", "辰"],
            "酉": ["巳", "丑"], "戌": ["寅", "午"], "亥": ["卯", "未"],
        }
        return sanfang_config[self.branch]

    def set_3fang4zheng(self, stars_3fang: List[Star], stars_opposite: List[Star]) -> None:
        self._3fang_list = stars_3fang
        self._opposite_list = stars_opposite

    def get_opposite_palace_branch(self) -> str:
        # 地支六冲
        six_clash = {
            "子": "午", "丑": "未", "寅": "申", "卯": "酉", "辰": "戌", "巳": "亥",
            "午": "子", "未": "丑", "申": "寅", "酉": "卯", "戌": "辰", "亥": "巳",
        }
        return six_clash[self.branch]

    def _get_star_self_transformation_str(self) -> str:
        return "".join(star.get_self_transformations()
                       for star in self.original if star.self_transformation)

    def _get_3fang_str(self) -> str:
        return "".join(str(star) for star in self._3fang_list)

    def _get_oppo_str(self) -> str:
        star_text = ""
        for star in self._opposite_list:
            star_text += str(star)
            if star.transformation == "忌" or star.decennial_transformation == "忌":
                star_text += "<忌冲>"
        return star_text

    def __str__(self) -> str:
        stars_str = "".join(f" - {star} <br>" for star in self.original)
        self_trans_str = self._get_star_self_transformation_str()
        neighbor_3fang_str = self._get_3fang_str()
        neighbor_oppo_str = self._get_oppo_str()
        opposite_branch = self.get_opposite_palace_branch()
        sanfang_branch = "".join(self.get_3fang_branch())
        cycl_str = f"{self.decennial_cycl[0]}~{self.decennial_cycl[1]}"
        if self.year_name:
            table_row = (
                f"| {self.year_name} | {self.decennial_name}| 本命{self.name} | {cycl_str} | "
                f"{self.stem}{self.branch} | {stars_str} | {self_trans_str} | "
                f"{opposite_branch} | {sanfang_branch} |"
            )
        elif self.decennial_name:
            table_row = (
                f"| {self.decennial_name}| 本命{self.name} | {cycl_str} | {self.stem}{self.branch} | "
                f"{stars_str} | {self_trans_str} | {opposite_branch} | {sanfang_branch} |"
            )
        else:
            table_row = (
                f"| {self.name} | {cycl_str} | {self.stem}{self.branch} | {stars_str} | "
                f"{self_trans_str}| {opposite_branch} | {sanfang_branch} |"
            )
        return table_row

    def to_dict(self) -> dict:
        return {
            "stem": self.stem,
            "branch": self.branch,
            "name": self.name,
            "decennial_name": self.decennial_name,
            "year_name": self.year_name,
            "month_name": self.month_name,
            "original": [star.to_dict() for star in self.original],
            "three_fang_names": [star.name for star in self._3fang_list],   # 三方星曜名
            "opposite_names": [star.name for star in self._opposite_list],  # 对宫星曜名
            "decennial_cycl": list(self.decennial_cycl) if self.decennial_cycl else [],
            "decennial_cycl_year_range": (
                [self.decennial_cycl_year_range.start, self.decennial_cycl_year_range.stop]
                if isinstance(self.decennial_cycl_year_range, range) else []
            ),
            "opposite_branch": self.get_opposite_palace_branch() if self.branch else "",
            "sanfang_branches": self.get_3fang_branch() if self.branch else [],
        }


class BirthChart:
    """本命盘：十二宫 + 大限索引。"""

    def __init__(self):
        self.palace_list: List[Palace] = []
        self.decennial_age_index: dict[range, tuple] = {}
        self.decennial_year_index: dict[range, tuple] = {}

    def add_palace(self, gong: Palace) -> None:
        if len(self.palace_list) <= 12:
            self.palace_list.append(gong)
        else:
            raise ValueError("命盘不能超过12个宫, 请检查参数")

    def get_palace_by_branch(self, branch: str) -> Palace | None:
        for palace in self.palace_list:
            if palace.branch == branch:
                return palace
        return None

    def set_3fang4zheng(self) -> None:
        for palace in self.palace_list:
            branches_3fang = palace.get_3fang_branch()
            stars_3fang: List[Star] = []
            for branch in branches_3fang:
                stars_3fang += self.get_palace_by_branch(branch).original
            opposite_branch = palace.get_opposite_palace_branch()
            stars_opposite = self.get_palace_by_branch(opposite_branch).original
            palace.set_3fang4zheng(stars_3fang, stars_opposite)

    def set_decennial_index(self) -> None:
        # 以年龄区间为 key（含止岁），以流年区间为 key
        decennial_index: dict[range, tuple] = {}
        decennial_year_index: dict[range, tuple] = {}
        for i, palace in enumerate(self.palace_list):
            age_key = range(palace.decennial_cycl[0], palace.decennial_cycl[1] + 1)
            decennial_index[age_key] = (palace, i)
            decennial_year_index[palace.decennial_cycl_year_range] = (palace, i)
        self.decennial_age_index = decennial_index
        self.decennial_year_index = decennial_year_index

    def _decennial_index_list(self, index: dict[range, tuple]) -> list[dict]:
        return [
            {
                "start": age_range.start,
                "end": age_range.stop - 1,
                "palace_index": palace_index,
                "palace_name": palace.name,
                "stem": palace.stem,
            }
            for age_range, (palace, palace_index) in index.items()
        ]

    def __str__(self) -> str:
        string = "本命盘基本情况:\n\n"
        string += "| 流年宫位 | 大运宫位 | 本命宫位 | 周期 | 宫位干支 | 星曜情况 | 自化情况 | 对宫 | 三方 |  \n"
        string += "| ------- | ------- | ------ | --- | ------ | ------- | ------ |  --- | --- |  \n"
        for palace in self.palace_list:
            string += str(palace) + "\n"
        return string

    def to_dict(self) -> dict:
        return {
            "palaces": [palace.to_dict() for palace in self.palace_list],
            "name_index": {p.name: i for i, p in enumerate(self.palace_list)},
            "decennial_age_index": self._decennial_index_list(self.decennial_age_index),
            "decennial_year_index": self._decennial_index_list(self.decennial_year_index),
        }


class Chart:
    """公开的排盘结果：本命盘 + 输入回执，可派生大限/流年/流月视图。"""

    def __init__(self, birth_chart: BirthChart, calendar_info: "CalendarInfo",
                 birth_month: int, birth_shichen: int, gender: str,
                 rules: RuleSet, input_receipt: dict):
        self.birth_chart = birth_chart
        self.calendar = calendar_info
        self.birth_month = birth_month
        self.birth_shichen = birth_shichen
        self.gender = gender
        self.rules = rules
        self.input_receipt = input_receipt

    def to_dict(self) -> dict:
        payload = {"schema": "ziwei_chart.v1", "input": self.input_receipt}
        payload.update(self.birth_chart.to_dict())
        return payload

    def horoscope(self, year: int | None = None, month: int | None = None,
                  is_leap: bool = False, age: int | None = None) -> "HoroscopeChart":
        """返回新的视图对象，不修改本命盘。

        - ``horoscope(year=Y)``：大限 + 流年。
        - ``horoscope(year=Y, month=M, is_leap=L)``：大限 + 流年 + 流月
          （与 suanqiu 生产端 ``_set_monthly_chart`` 语义一致）。
        - ``horoscope(age=N)``：仅按年龄切大限。
        """
        from .horoscope import apply_decennial, apply_month, apply_year

        if month is not None and year is None:
            raise ValueError("流月必须随流年一起选择 (year=...)")
        if year is None and age is None:
            raise ValueError("horoscope 需要 year 或 age")

        copied = deepcopy(self.birth_chart)
        monthly_meta = None
        if month is not None:
            ranges = apply_decennial(copied, year=year)
            apply_year(copied, year=year, rules=self.rules)
            monthly_meta = apply_month(
                copied, year=year, month=month, is_leap=is_leap,
                birth_month=self.birth_month, birth_shichen=self.birth_shichen,
                rules=self.rules,
            )
            mode = "monthly"
        else:
            ranges = apply_decennial(copied, year=year, age=age)
            if year is not None:
                apply_year(copied, year=year, rules=self.rules)
            mode = "yearly" if year is not None else "decennial"

        return HoroscopeChart(
            birth_chart=copied, mode=mode, year=year, month=month, is_leap=is_leap,
            monthly=monthly_meta, age=age, age_range=ranges["age_range"],
            year_range=ranges["year_range"], input_receipt=self.input_receipt,
        )


class HoroscopeChart:
    def __init__(self, birth_chart: BirthChart, mode: str, year: int | None,
                 month: int | None, is_leap: bool, monthly: dict | None,
                 age: int | None = None, age_range: str = "", year_range: str = "",
                 input_receipt: dict | None = None):
        self.birth_chart = birth_chart
        self.mode = mode
        self.year = year
        self.month = month
        self.is_leap = is_leap
        self.monthly = monthly  # 流月斗君元数据，非流月视图时为 None
        self.age = age
        self.age_range = age_range      # 所在大限的年龄段，如 "25-34"
        self.year_range = year_range    # 所在大限的年份段，如 "2018-2027"
        self.input_receipt = input_receipt or {}

    def to_dict(self) -> dict:
        payload = {
            "schema": "ziwei_chart.v1",
            "input": self.input_receipt,
            "horoscope": {
                "mode": self.mode,
                "year": self.year,
                "month": self.month,
                "is_leap": self.is_leap,
                "age": self.age,
                "age_range": self.age_range,
                "year_range": self.year_range,
                "monthly": self.monthly,
            },
        }
        payload.update(self.birth_chart.to_dict())
        return payload
