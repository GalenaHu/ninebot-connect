"""Minimal persisted authentication and projected vehicle data."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, repr=False)
class AccountSession:
    access_token: str
    refresh_token: str
    uuid: str
    business_uid: str
    device_id: str

    def __repr__(self) -> str:
        return "AccountSession(<redacted>)"

    def to_storage(self) -> dict[str, Any]:
        return {
            key: getattr(self, key)
            for key in (
                "access_token",
                "refresh_token",
                "uuid",
                "business_uid",
                "device_id",
            )
        }

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> AccountSession:
        required = ("access_token", "uuid", "business_uid", "device_id")
        if any(not isinstance(data.get(key), str) or not data[key] for key in required):
            raise ValueError("Incomplete saved session")
        refresh = data.get("refresh_token")
        return cls(
            access_token=data["access_token"],
            refresh_token=refresh if isinstance(refresh, str) else "",
            uuid=data["uuid"],
            business_uid=data["business_uid"],
            device_id=data["device_id"],
        )


@dataclass(frozen=True)
class Vehicle:
    sn: str
    name: str
    model: str
    vehicle_type: str


@dataclass(frozen=True)
class VehicleState:
    battery: float | None = None
    range_km: float | None = None
    charging: bool | None = None
    main_battery_online: bool | None = None
    lock_status: int | None = None
    mileage_km: float | None = None
    reported_at: datetime | None = None
    location_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    available: bool = True

    def unavailable(self) -> VehicleState:
        return replace(self, available=False)


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
    except ValueError, OverflowError:
        return None
    return result if math.isfinite(result) else None


def flag(value: Any) -> bool | None:
    parsed = number(value)
    return bool(parsed) if parsed in (0, 1) else None


def timestamp(value: Any) -> datetime | None:
    parsed = number(value)
    if parsed is None or parsed <= 0:
        return None
    if parsed >= 1_000_000_000_000:
        parsed /= 1000
    try:
        return datetime.fromtimestamp(parsed, UTC)
    except ValueError, OverflowError, OSError:
        return None


def project_vehicle_state(data: dict[str, Any]) -> VehicleState:
    """Keep only display fields. APK LocationCard explicitly converts these WGS84
    coordinates to GCJ02 for its Chinese map; HA consumes the original WGS84.
    """
    battery = number(data.get("dump_energy"))
    distance = number(data.get("precise_estimate_mileage"))
    mileage = number(data.get("total_mileage"))
    lat, lon = number(data.get("latitude")), number(data.get("longitude"))
    if (
        lat is None
        or lon is None
        or not -90 <= lat <= 90
        or not -180 <= lon <= 180
        or (lat == 0 and lon == 0)
    ):
        lat = lon = None
    return VehicleState(
        battery=battery if battery is not None and 0 <= battery <= 100 else None,
        range_km=distance if distance is not None and distance >= 0 else None,
        charging=flag(data.get("charging")),
        main_battery_online=flag(data.get("pwr")),
        lock_status=int(value) if (value := number(data.get("lock_status"))) in (0, 1) else None,
        mileage_km=mileage if mileage is not None and mileage >= 0 else None,
        reported_at=timestamp(data.get("lastupdatetime")),
        location_at=timestamp(data.get("gnss_time")),
        latitude=lat,
        longitude=lon,
    )
