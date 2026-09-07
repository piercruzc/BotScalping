from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULTS = {
    "symbol": "XAUUSD",
    "magic": 260907,
    "lot_size": 0.01,
    "pip_size": 0.1,
    "max_spread_pips": 35.0,
    "entry_tolerance": 0.2,
    "chase_buffer_pips": 15.0,
    "be_cushion_pips": 2.0,
    "deviation_points": 50,
    "trail_enabled": True,
    "trail_start_pips": 80.0,
    "trail_distance_pips": 40.0,
    "split_take_profits": False,
    "max_concurrent_signals": 1,
    "dry_run": True,
    "telegram_enabled": True,
    "operating_mode": "demo",
    "live_confirmed": False,
    "panel": {"enabled": True, "host": "127.0.0.1", "port": 8787},
}

EDITABLE_FIELDS = {
    "symbol",
    "lot_size",
    "pip_size",
    "max_spread_pips",
    "entry_tolerance",
    "chase_buffer_pips",
    "be_cushion_pips",
    "deviation_points",
    "trail_enabled",
    "trail_start_pips",
    "trail_distance_pips",
    "dry_run",
    "telegram_enabled",
    "split_take_profits",
}


@dataclass
class Settings:
    symbol: str = "XAUUSD"
    magic: int = 260907
    lot_size: float = 0.01
    pip_size: float = 0.1
    max_spread_pips: float = 35.0
    entry_tolerance: float = 0.2
    chase_buffer_pips: float = 15.0
    be_cushion_pips: float = 2.0
    deviation_points: int = 50
    trail_enabled: bool = True
    trail_start_pips: float = 80.0
    trail_distance_pips: float = 40.0
    split_take_profits: bool = False
    max_concurrent_signals: int = 1
    dry_run: bool = True
    telegram_enabled: bool = True
    operating_mode: str = "demo"
    live_confirmed: bool = False
    panel_host: str = "127.0.0.1"
    panel_port: int = 8787

    @property
    def telegram_active(self) -> bool:
        return self.operating_mode == "real" or self.telegram_enabled

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "magic": self.magic,
            "lot_size": self.lot_size,
            "pip_size": self.pip_size,
            "max_spread_pips": self.max_spread_pips,
            "entry_tolerance": self.entry_tolerance,
            "chase_buffer_pips": self.chase_buffer_pips,
            "be_cushion_pips": self.be_cushion_pips,
            "deviation_points": self.deviation_points,
            "trail_enabled": self.trail_enabled,
            "trail_start_pips": self.trail_start_pips,
            "trail_distance_pips": self.trail_distance_pips,
            "split_take_profits": self.split_take_profits,
            "max_concurrent_signals": self.max_concurrent_signals,
            "dry_run": self.dry_run,
            "telegram_enabled": self.telegram_enabled,
            "telegram_forced": self.operating_mode == "real",
            "operating_mode": self.operating_mode,
            "live_confirmed": self.live_confirmed,
            "panel_host": self.panel_host,
            "panel_port": self.panel_port,
        }


class ConfigStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._settings = Settings()
        self.reload()

    def get(self) -> Settings:
        with self._lock:
            return self._settings

    def reload(self) -> Settings:
        with self._lock:
            data: dict[str, Any] = {}
            if self.path.exists():
                loaded = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
                if not isinstance(loaded, dict):
                    raise ValueError("config.yaml inválido")
                data = loaded
            self._settings = _from_yaml(data)
            return self._settings

    def update(self, changes: dict[str, Any]) -> Settings:
        with self._lock:
            current = self._settings
            payload = {key: getattr(current, key) for key in EDITABLE_FIELDS}
            for key, value in changes.items():
                if key not in EDITABLE_FIELDS:
                    continue
                payload[key] = _coerce(key, value)
            if current.operating_mode == "real":
                payload["telegram_enabled"] = True
            merged = asdict(current)
            merged.update(payload)
            self._settings = Settings(**_normalize(merged))
            self._persist()
            return self._settings

    def set_mode(self, mode: str, live_confirmed: bool | None = None) -> Settings:
        if mode not in {"demo", "real"}:
            raise ValueError("El modo debe ser demo o real")
        with self._lock:
            confirmed = self._settings.live_confirmed if live_confirmed is None else live_confirmed
            if mode == "demo":
                confirmed = False
            merged = asdict(self._settings)
            merged["operating_mode"] = mode
            merged["live_confirmed"] = confirmed
            if mode == "real":
                merged["telegram_enabled"] = True
            self._settings = Settings(**_normalize(merged))
            self._persist()
            return self._settings

    def _persist(self) -> None:
        settings = self._settings
        data = {
            "symbol": settings.symbol,
            "magic": settings.magic,
            "lot_size": settings.lot_size,
            "pip_size": settings.pip_size,
            "max_spread_pips": settings.max_spread_pips,
            "entry_tolerance": settings.entry_tolerance,
            "chase_buffer_pips": settings.chase_buffer_pips,
            "be_cushion_pips": settings.be_cushion_pips,
            "deviation_points": settings.deviation_points,
            "trail_enabled": settings.trail_enabled,
            "trail_start_pips": settings.trail_start_pips,
            "trail_distance_pips": settings.trail_distance_pips,
            "split_take_profits": settings.split_take_profits,
            "max_concurrent_signals": settings.max_concurrent_signals,
            "dry_run": settings.dry_run,
            "telegram_enabled": settings.telegram_enabled,
            "operating_mode": settings.operating_mode,
            "live_confirmed": settings.live_confirmed,
            "panel": {
                "enabled": True,
                "host": settings.panel_host,
                "port": settings.panel_port,
            },
        }
        self.path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )


def _from_yaml(data: dict[str, Any]) -> Settings:
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k != "panel"})
    panel = data.get("panel") or DEFAULTS["panel"]
    merged["panel_host"] = panel.get("host", "127.0.0.1")
    merged["panel_port"] = panel.get("port", 8787)
    return Settings(**_normalize(merged))


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    allowed = set(Settings.__dataclass_fields__)
    clean = {key: data[key] for key in allowed if key in data}
    clean.setdefault("panel_host", "127.0.0.1")
    clean.setdefault("panel_port", 8787)
    return clean


def _coerce(key: str, value: Any) -> Any:
    if key in {
        "lot_size",
        "pip_size",
        "max_spread_pips",
        "entry_tolerance",
        "chase_buffer_pips",
        "be_cushion_pips",
        "trail_start_pips",
        "trail_distance_pips",
    }:
        return float(value)
    if key == "deviation_points":
        return int(value)
    if key in {"dry_run", "telegram_enabled", "trail_enabled", "split_take_profits"}:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if key == "symbol":
        return str(value).strip().upper()
    return value
