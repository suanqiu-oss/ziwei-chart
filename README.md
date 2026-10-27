# ziwei-chart

确定性紫微斗数排盘库：输入出生时刻（可带经纬度换算真太阳时），输出生辰十二宫
安星、大限索引与流年/流月视图的带版本号 JSON（`ziwei_chart.v1`）。
不含任何 AI 解读与星曜释义文本。

纯 Python；日历后端为 [lunar-python](https://github.com/6tail/lunar-python)。
真太阳时（天文中天法）是可选依赖，需 `pip install ziwei-chart[solar]`。

## 安装

```bash
pip install ziwei-chart          # 基础（民用时间排盘）
pip install ziwei-chart[solar]   # + 真太阳时（skyfield）
```

## 使用

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from ziwei_chart import BirthInput, CalendarRules, cast_chart

chart = cast_chart(BirthInput(
    datetime=datetime(2004, 4, 25, 9, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
    gender="男",
    longitude=116.39,          # 可选；给了就换算真太阳时（需 [solar]）
    latitude=39.90,
))
chart.to_dict()                                   # 本命盘（ziwei_chart.v1）
chart.horoscope(year=2026).to_dict()              # 大限 + 流年
chart.horoscope(year=2026, month=3, is_leap=False).to_dict()  # 流月
```

已有八字/农历串的应用可以走预算好的日历路径：

```python
chart = cast_chart(BirthInput(
    gender="女",
    bazi="甲申戊辰甲戌己巳",
    lunar_date_str="2004-03-07 09:20:00",
))
```

`BirthInput.datetime` 必须带 IANA 时区（如 `ZoneInfo("Asia/Shanghai")`）。
固定偏移的 `datetime.timezone(timedelta(hours=8))` 会被拒绝，因为真太阳时和
历史夏令时都要按时区名换算。

## 默认口径（流派差异参数化）

- `CalendarRules(day_rule="zi-early", time_rule="next-day")`：子初换日、
  夜子归次日（与现行 suanqiu 口径一致）。可选 `day_rule="midnight" |
  "solar-midnight"`、`time_rule="midnight" | "prev-day"`。
- 农历日期本身按民用午夜切日，不跟随日柱换日口径。
- 四化表可通过 `rules=` 注入自定义版本（如庚干派别分歧）：
  `cast_chart(inp, rules=RuleSet.default().with_sihua(my_table))`。

## 真太阳时星历

`[solar]` extra 依赖 skyfield；DE421 星历（约 17 MB）按以下顺序解析：
`eph_path` 参数 → 环境变量 `ZIWEI_CHART_EPHEMERIS` → 首次使用时自动下载到
用户缓存目录。

## 输出契约

顶层 `schema` 固定为 `ziwei_chart.v1`，JSON Schema 随包发布于
`ziwei_chart/schema/ziwei_chart.v1.json`。与旧实现的差异：

| 字段 | 处理 |
| --- | --- |
| `schema` / `input` | 新增；本命盘和大限/流年/流月视图都带 |
| `horoscope` | 新增，仅视图带：`mode`、`year`、`month`、`is_leap`、`age`，所在大限的 `age_range` / `year_range`，流月斗君元数据 `monthly` |
| `Star.property`、`Palace.palace_implication` | 删除（释义文本由应用层补回） |
| `decennial_age_index` 等 range 字符串键 | 改为 `[{start, end, palace_index, ...}]` 列表 |

字段有破坏性变更时升级到 v2。

## 许可证

Apache-2.0，全文见 `LICENSE`。规则表为项目自行整理，不含第三方代码。
