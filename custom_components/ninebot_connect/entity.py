"""Shared HA entity identity, device grouping and vehicle availability."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NinebotCoordinator
from .models import VehicleState


class NinebotEntity(CoordinatorEntity[NinebotCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: NinebotCoordinator, sn: str, key: str) -> None:
        super().__init__(coordinator)
        self.sn = sn
        self._card_role = key
        session = coordinator.client.session
        assert session is not None
        identity = f"{session.uuid}:{sn}"
        self._attr_unique_id = f"{identity}:{key}"
        vehicle = coordinator.vehicles[sn]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity)},
            name=vehicle.name,
            manufacturer="Segway-Ninebot",
            model=vehicle.model,
        )

    @property
    def vehicle_state(self) -> VehicleState:
        return (self.coordinator.data or {}).get(self.sn, VehicleState(available=False))

    @property
    def available(self) -> bool:
        return super().available and self.vehicle_state.available

    @property
    def extra_state_attributes(self) -> dict:
        return {"ninebot_connect_role": self._card_role}
