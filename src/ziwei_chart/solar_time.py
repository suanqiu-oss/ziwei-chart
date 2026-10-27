"""True solar time via Skyfield's meridian-transit method.

Optional dependency — install with the ``[solar]`` extra::

    pip install ziwei-chart[solar]

The DE421 ephemeris (~17 MB) is resolved in this order:

1. explicit ``eph_path`` argument,
2. ``ZIWEI_CHART_EPHEMERIS`` environment variable,
3. automatic download into a per-user cache directory on first use.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_EPH_FILENAME = "de421.bsp"


def _load_ephemeris(eph_path: str | None):
    try:
        from skyfield.api import Loader, load
    except ImportError as exc:  # pragma: no cover - exercised without [solar]
        raise ImportError(
            "True solar time needs the [solar] extra: pip install ziwei-chart[solar]"
        ) from exc

    candidates = [eph_path, os.environ.get("ZIWEI_CHART_EPHEMERIS")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return load(candidate)
    cache_dir = Path.home() / ".cache" / "ziwei-chart"
    cache_dir.mkdir(parents=True, exist_ok=True)
    loader = Loader(str(cache_dir), verbose=False)
    return loader(_EPH_FILENAME)


def resolve_true_solar_time(dt_local: datetime, lat: float, lon: float, tz: str,
                            eph_path: str | None = None) -> datetime:
    """
    用 Skyfield 天文内核（子午圈过境法）计算真太阳时。

    Args:
        dt_local: 出生地民用时间（naive 或 aware 均可，按 tz 解释）
        lat, lon: 出生地纬度/东经度数
        tz: IANA 时区名（如 "Asia/Shanghai"）
        eph_path: DE421 星历文件路径；缺省按模块文档的顺序解析

    Returns:
        带时区的 datetime，表示真太阳时（当地真太阳正午 = 12:00）
    """
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=ZoneInfo(tz))
    else:
        dt_local = dt_local.astimezone(ZoneInfo(tz))
    dt_utc = dt_local.astimezone(ZoneInfo("UTC"))

    from skyfield import almanac
    from skyfield.api import wgs84
    from skyfield.api import load as _load

    ts = _load.timescale()
    t = ts.from_datetime(dt_utc)
    eph = _load_ephemeris(eph_path)
    topos = wgs84.latlon(latitude_degrees=lat, longitude_degrees=lon)

    t0 = ts.from_datetime(dt_utc - timedelta(hours=36))
    t1 = ts.from_datetime(dt_utc + timedelta(hours=36))
    f = almanac.meridian_transits(eph, eph["sun"], topos)
    times, events = almanac.find_discrete(t0, t1, f)
    # events==1 为上中天（真太阳正午）
    transits = [ti for ti, ev in zip(times, events) if ev == 1]
    if not transits:
        raise RuntimeError("no solar meridian transit found in the ±36h window")
    solar_noon = min(transits, key=lambda ti: abs(ti.tt - t.tt))

    delta_hours = (t.tt - solar_noon.tt) * 24.0
    ast_hour_float = (12.0 + delta_hours) % 24.0

    civil_hour_float = dt_local.hour + dt_local.minute / 60.0 + dt_local.second / 3600.0
    delta_minutes = (ast_hour_float - civil_hour_float) * 60.0
    return (dt_local + timedelta(minutes=delta_minutes)).astimezone(ZoneInfo(tz))
