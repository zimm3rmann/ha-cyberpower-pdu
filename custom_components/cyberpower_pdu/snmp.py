from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice
import os
from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    get_cmd,
    set_cmd,
    USM_AUTH_HMAC96_MD5,
    USM_AUTH_HMAC96_SHA,
    USM_AUTH_HMAC128_SHA224,
    USM_AUTH_HMAC192_SHA256,
    USM_AUTH_HMAC256_SHA384,
    USM_AUTH_HMAC384_SHA512,
    USM_AUTH_NONE,
    USM_PRIV_CBC56_DES,
    USM_PRIV_CBC168_3DES,
    USM_PRIV_CFB128_AES,
    USM_PRIV_CFB192_AES,
    USM_PRIV_CFB256_AES,
    USM_PRIV_NONE,
)
from pysnmp.proto.rfc1902 import Integer

from .const import (
    AUTH_MD5,
    AUTH_NONE,
    AUTH_SHA,
    AUTH_SHA224,
    AUTH_SHA256,
    AUTH_SHA384,
    AUTH_SHA512,
    DEFAULT_OUTLET_COUNT,
    OUTLET_COMMAND_OFF,
    OUTLET_COMMAND_ON,
    OUTLET_COMMAND_REBOOT,
    OUTLET_STATE_ON,
    PRIVACY_3DES,
    PRIVACY_AES,
    PRIVACY_AES192,
    PRIVACY_AES256,
    PRIVACY_DES,
    PRIVACY_NONE,
    SNMP_V1,
    SNMP_V2C,
)

MAX_OUTLETS = 64
GET_CHUNK_SIZE = 4

EPDU_IDENT = "1.3.6.1.4.1.3808.1.1.3.1"
EPDU_LOAD_STATUS = "1.3.6.1.4.1.3808.1.1.3.2.3.1.1"
EPDU_OUTLET_DEVICE = "1.3.6.1.4.1.3808.1.1.3.3.1"
EPDU_OUTLET_CONTROL = "1.3.6.1.4.1.3808.1.1.3.3.3.1.1"
EPDU_OUTLET_STATUS = "1.3.6.1.4.1.3808.1.1.3.3.5.1.1"

ATS_IDENT = "1.3.6.1.4.1.3808.1.1.5.1"
ATS_OUTLET_DEVICE = "1.3.6.1.4.1.3808.1.1.5.6.1"
ATS_OUTLET_CONTROL = "1.3.6.1.4.1.3808.1.1.5.6.5.1"
ATS_OUTLET_STATUS = "1.3.6.1.4.1.3808.1.1.5.6.3.1"

DEVICE_OIDS = {
    "name": f"{EPDU_IDENT}.1.0",
    "hardware": f"{EPDU_IDENT}.2.0",
    "firmware": f"{EPDU_IDENT}.3.0",
    "model": f"{EPDU_IDENT}.5.0",
    "serial": f"{EPDU_IDENT}.6.0",
    "outlet_count": f"{EPDU_IDENT}.8.0",
    "controlled_outlets": f"{EPDU_OUTLET_DEVICE}.3.0",
}

ATS_DEVICE_OIDS = {
    "name": f"{ATS_IDENT}.1.0",
    "model": f"{ATS_IDENT}.2.0",
    "hardware": f"{ATS_IDENT}.3.0",
    "firmware": f"{ATS_IDENT}.4.0",
    "serial": f"{ATS_IDENT}.5.0",
    "outlet_count": f"{ATS_IDENT}.9.0",
    "controlled_outlets": f"{ATS_OUTLET_DEVICE}.2.0",
}

TOTAL_OIDS = {
    "current": f"{EPDU_LOAD_STATUS}.2.1",
    "voltage": f"{EPDU_LOAD_STATUS}.6.1",
    "power": f"{EPDU_LOAD_STATUS}.7.1",
    "apparent_power": f"{EPDU_LOAD_STATUS}.8.1",
    "power_factor": f"{EPDU_LOAD_STATUS}.9.1",
    "energy": f"{EPDU_LOAD_STATUS}.10.1",
}

OUTLET_STATUS_COLUMNS = {
    "name": 2,
    "phase": 3,
    "state": 4,
    "command_pending": 5,
    "bank": 6,
    "current": 7,
    "power": 8,
    "alarm": 9,
    "peak_power": 10,
    "energy": 13,
}

ATS_OUTLET_STATUS_COLUMNS = {
    "name": 2,
    "state": 3,
    "command_pending": 4,
    "phase": 5,
    "bank": 6,
}

OUTLET_CONTROL_COMMAND_COLUMN = 4
ATS_OUTLET_CONTROL_COMMAND_COLUMN = 3
MIB_BRANCH_EPDU = "epdu"
MIB_BRANCH_ATS = "ats"

AUTH_PROTOCOL_MAP = {
    AUTH_NONE: USM_AUTH_NONE,
    AUTH_MD5: USM_AUTH_HMAC96_MD5,
    AUTH_SHA: USM_AUTH_HMAC96_SHA,
    AUTH_SHA224: USM_AUTH_HMAC128_SHA224,
    AUTH_SHA256: USM_AUTH_HMAC192_SHA256,
    AUTH_SHA384: USM_AUTH_HMAC256_SHA384,
    AUTH_SHA512: USM_AUTH_HMAC384_SHA512,
}

PRIVACY_PROTOCOL_MAP = {
    PRIVACY_NONE: USM_PRIV_NONE,
    PRIVACY_DES: USM_PRIV_CBC56_DES,
    PRIVACY_3DES: USM_PRIV_CBC168_3DES,
    PRIVACY_AES: USM_PRIV_CFB128_AES,
    PRIVACY_AES192: USM_PRIV_CFB192_AES,
    PRIVACY_AES256: USM_PRIV_CFB256_AES,
}


class CyberPowerPduError(Exception):
    pass


class CyberPowerPduConnectionError(CyberPowerPduError):
    pass


class CyberPowerPduSnmpError(CyberPowerPduError):
    def __init__(self, status: str, oid: str | None = None) -> None:
        self.status = status
        self.oid = oid
        message = status if oid is None else f"{status} at {oid}"
        super().__init__(message)

    @property
    def is_missing_oid(self) -> bool:
        return "nosuch" in self.status.replace(" ", "").lower()


@dataclass(slots=True, frozen=True)
class CyberPowerPduConfig:
    host: str
    port: int
    version: str
    community: str | None
    username: str | None
    auth_protocol: str
    auth_key: str | None
    privacy_protocol: str
    privacy_key: str | None
    context_name: str
    timeout: float
    retries: int


@dataclass(slots=True, frozen=True)
class CyberPowerPduDevice:
    host: str
    mib_branch: str
    name: str | None
    model: str | None
    serial: str | None
    firmware: str | None
    hardware: str | None
    outlet_count: int | None
    controlled_outlets: int | None


@dataclass(slots=True, frozen=True)
class CyberPowerPduOutlet:
    index: int
    name: str
    state: int | None
    command_pending: bool | None
    current: float | None
    power: int | None
    apparent_power: float | None
    peak_power: int | None
    energy: float | None
    phase: int | None
    bank: int | None
    alarm: int | None

    @property
    def is_on(self) -> bool | None:
        if self.state is None:
            return None
        return self.state == OUTLET_STATE_ON


@dataclass(slots=True, frozen=True)
class CyberPowerPduData:
    device: CyberPowerPduDevice
    outlets: tuple[CyberPowerPduOutlet, ...]
    current: float | None
    voltage: float | None
    power: int | None
    apparent_power: int | None
    power_factor: float | None
    energy: float | None

    def outlet(self, index: int) -> CyberPowerPduOutlet | None:
        return next((outlet for outlet in self.outlets if outlet.index == index), None)


class CyberPowerPduClient:
    def __init__(self, config: CyberPowerPduConfig) -> None:
        self._config = config
        self._engine: SnmpEngine | None = None
        self._lock = asyncio.Lock()
        self._mib_branch = MIB_BRANCH_EPDU

    async def async_close(self) -> None:
        if self._engine is not None:
            self._engine.close_dispatcher()

    async def async_fetch_device_info(self) -> CyberPowerPduDevice:
        async with self._lock:
            return await self._fetch_device_info_locked()

    async def async_fetch(self) -> CyberPowerPduData:
        async with self._lock:
            device = await self._fetch_device_info_locked()
            count = _bounded_outlet_count(
                device.controlled_outlets or device.outlet_count or DEFAULT_OUTLET_COUNT
            )
            if device.mib_branch == MIB_BRANCH_ATS:
                outlet_values = await self._get_many_locked(_ats_outlet_status_oids(count))
                outlets = tuple(
                    _build_ats_outlet(index, outlet_values) for index in range(1, count + 1)
                )
                return CyberPowerPduData(
                    device=device,
                    outlets=outlets,
                    current=None,
                    voltage=None,
                    power=None,
                    apparent_power=None,
                    power_factor=None,
                    energy=None,
            )

            total_values = await self._get_many_locked(TOTAL_OIDS.values())
            voltage = _as_scaled_number(total_values.get(TOTAL_OIDS["voltage"]), 10)
            outlet_values = await self._get_many_locked(_outlet_status_oids(count))
            outlets = tuple(
                _build_epdu_outlet(index, outlet_values, voltage)
                for index in range(1, count + 1)
            )

            return CyberPowerPduData(
                device=device,
                outlets=outlets,
                current=_as_scaled_number(total_values.get(TOTAL_OIDS["current"]), 10),
                voltage=voltage,
                power=_as_int(total_values.get(TOTAL_OIDS["power"])),
                apparent_power=_as_int(total_values.get(TOTAL_OIDS["apparent_power"])),
                power_factor=_as_scaled_number(total_values.get(TOTAL_OIDS["power_factor"]), 100),
                energy=_as_scaled_number(total_values.get(TOTAL_OIDS["energy"]), 10),
            )

    async def async_set_outlet_power(self, index: int, on: bool) -> None:
        command = OUTLET_COMMAND_ON if on else OUTLET_COMMAND_OFF
        await self._set_outlet_command(index, command)

    async def async_power_cycle_outlet(self, index: int) -> None:
        await self._set_outlet_command(index, OUTLET_COMMAND_REBOOT)

    async def _set_outlet_command(self, index: int, command: int) -> None:
        async with self._lock:
            if self._mib_branch == MIB_BRANCH_ATS:
                oid = f"{ATS_OUTLET_CONTROL}.{ATS_OUTLET_CONTROL_COMMAND_COLUMN}.{index}"
            else:
                oid = f"{EPDU_OUTLET_CONTROL}.{OUTLET_CONTROL_COMMAND_COLUMN}.{index}"
            await self._set_int_locked(oid, command)

    async def _fetch_device_info_locked(self) -> CyberPowerPduDevice:
        values = await self._get_many_locked(DEVICE_OIDS.values())
        epdu_device = _build_device(self._config.host, MIB_BRANCH_EPDU, DEVICE_OIDS, values)
        if epdu_device.outlet_count or epdu_device.controlled_outlets:
            self._mib_branch = MIB_BRANCH_EPDU
            return epdu_device

        values = await self._get_many_locked(ATS_DEVICE_OIDS.values())
        ats_device = _build_device(self._config.host, MIB_BRANCH_ATS, ATS_DEVICE_OIDS, values)
        if _device_has_data(ats_device):
            self._mib_branch = MIB_BRANCH_ATS
            return ats_device

        if _device_has_data(epdu_device):
            self._mib_branch = MIB_BRANCH_EPDU
            return epdu_device
        return ats_device

    async def _get_many_locked(self, oids: Iterable[str]) -> dict[str, Any | None]:
        results: dict[str, Any | None] = {}
        for chunk in _chunks(oids, GET_CHUNK_SIZE):
            try:
                results.update(await self._get_chunk_locked(chunk))
            except CyberPowerPduSnmpError as err:
                if err.is_missing_oid and len(chunk) == 1:
                    results[chunk[0]] = None
                    continue
                if not err.is_missing_oid:
                    raise
                for oid in chunk:
                    try:
                        results.update(await self._get_chunk_locked((oid,)))
                    except CyberPowerPduSnmpError as single_err:
                        if single_err.is_missing_oid:
                            results[oid] = None
                        else:
                            raise
        return results

    async def _get_chunk_locked(self, oids: tuple[str, ...]) -> dict[str, Any | None]:
        error_indication, error_status, error_index, var_binds = await get_cmd(
            await self._async_engine(),
            self._auth_data(),
            await self._transport(),
            self._context_data(),
            *(ObjectType(ObjectIdentity(oid)) for oid in oids),
            lookupMib=False,
        )
        _raise_on_error(error_indication, error_status, error_index, var_binds)
        return {
            oid: _normalise_snmp_value(value)
            for oid, (_, value) in zip(oids, var_binds, strict=False)
        }

    async def _set_int_locked(self, oid: str, value: int) -> None:
        error_indication, error_status, error_index, var_binds = await set_cmd(
            await self._async_engine(),
            self._auth_data(),
            await self._transport(),
            self._context_data(),
            ObjectType(ObjectIdentity(oid), Integer(value)),
            lookupMib=False,
        )
        _raise_on_error(error_indication, error_status, error_index, var_binds)

    async def _async_engine(self) -> SnmpEngine:
        if self._engine is None:
            loop = asyncio.get_running_loop()
            self._engine = await loop.run_in_executor(None, _create_snmp_engine)
        return self._engine

    async def _transport(self) -> UdpTransportTarget:
        return await UdpTransportTarget.create(
            (self._config.host, self._config.port),
            timeout=self._config.timeout,
            retries=self._config.retries,
        )

    def _context_data(self) -> ContextData:
        return ContextData(contextName=self._config.context_name or "")

    def _auth_data(self) -> CommunityData | UsmUserData:
        if self._config.version == SNMP_V1:
            return CommunityData(self._config.community or "", mpModel=0)
        if self._config.version == SNMP_V2C:
            return CommunityData(self._config.community or "", mpModel=1)
        return UsmUserData(
            self._config.username or "",
            authKey=self._config.auth_key or None,
            privKey=self._config.privacy_key or None,
            authProtocol=AUTH_PROTOCOL_MAP[self._config.auth_protocol],
            privProtocol=PRIVACY_PROTOCOL_MAP[self._config.privacy_protocol],
        )


def _raise_on_error(
    error_indication: Any,
    error_status: Any,
    error_index: Any,
    var_binds: Any,
) -> None:
    if error_indication:
        raise CyberPowerPduConnectionError(str(error_indication))
    if error_status:
        status = error_status.prettyPrint()
        oid = None
        if error_index:
            try:
                oid = var_binds[int(error_index) - 1][0].prettyPrint()
            except (IndexError, TypeError, ValueError):
                oid = None
        raise CyberPowerPduSnmpError(status, oid)


def _create_snmp_engine() -> SnmpEngine:
    engine = SnmpEngine()
    mib_builder = engine.message_dispatcher.mib_instrum_controller.get_mib_builder()
    import pysnmp.smi.mibs as mibs
    import pysnmp.smi.mibs.instances as mib_instances

    mib_builder.load_modules(
        *_mib_module_names(mibs.__path__[0]),
        *_mib_module_names(mib_instances.__path__[0]),
    )
    return engine


def _mib_module_names(path: str) -> tuple[str, ...]:
    return tuple(
        filename[:-3]
        for filename in os.listdir(path)
        if filename.endswith(".py") and filename != "__init__.py"
    )


def _outlet_status_oids(count: int) -> tuple[str, ...]:
    return tuple(
        f"{EPDU_OUTLET_STATUS}.{column}.{index}"
        for index in range(1, count + 1)
        for column in OUTLET_STATUS_COLUMNS.values()
    )


def _ats_outlet_status_oids(count: int) -> tuple[str, ...]:
    return tuple(
        f"{ATS_OUTLET_STATUS}.{column}.{index}"
        for index in range(1, count + 1)
        for column in ATS_OUTLET_STATUS_COLUMNS.values()
    )


def _build_device(
    host: str,
    mib_branch: str,
    oids: dict[str, str],
    values: dict[str, Any | None],
) -> CyberPowerPduDevice:
    return CyberPowerPduDevice(
        host=host,
        mib_branch=mib_branch,
        name=_as_text(values.get(oids["name"])),
        model=_as_text(values.get(oids["model"])),
        serial=_as_text(values.get(oids["serial"])),
        firmware=_as_text(values.get(oids["firmware"])),
        hardware=_as_text(values.get(oids["hardware"])),
        outlet_count=_as_int(values.get(oids["outlet_count"])),
        controlled_outlets=_as_int(values.get(oids["controlled_outlets"])),
    )


def _device_has_data(device: CyberPowerPduDevice) -> bool:
    return any(
        (
            device.name,
            device.model,
            device.serial,
            device.outlet_count,
            device.controlled_outlets,
        )
    )


def _build_epdu_outlet(
    index: int,
    values: dict[str, Any | None],
    voltage: float | None,
) -> CyberPowerPduOutlet:
    def value(name: str) -> Any | None:
        return values.get(f"{EPDU_OUTLET_STATUS}.{OUTLET_STATUS_COLUMNS[name]}.{index}")

    name = _as_text(value("name")) or f"Outlet {index}"
    current = _as_scaled_number(value("current"), 100)
    power = _as_int(value("power"))
    apparent_power = _apparent_power(current, voltage)
    return CyberPowerPduOutlet(
        index=index,
        name=name,
        state=_as_int(value("state")),
        command_pending=_as_pending(value("command_pending")),
        current=current,
        power=_normalise_outlet_power(power, current),
        apparent_power=apparent_power,
        peak_power=_as_int(value("peak_power")),
        energy=_as_scaled_number(value("energy"), 10),
        phase=_as_int(value("phase")),
        bank=_as_int(value("bank")),
        alarm=_as_int(value("alarm")),
    )


def _build_ats_outlet(index: int, values: dict[str, Any | None]) -> CyberPowerPduOutlet:
    def value(name: str) -> Any | None:
        return values.get(f"{ATS_OUTLET_STATUS}.{ATS_OUTLET_STATUS_COLUMNS[name]}.{index}")

    name = _as_text(value("name")) or f"Outlet {index}"
    return CyberPowerPduOutlet(
        index=index,
        name=name,
        state=_as_int(value("state")),
        command_pending=_as_pending(value("command_pending")),
        current=None,
        power=None,
        apparent_power=None,
        peak_power=None,
        energy=None,
        phase=_as_int(value("phase")),
        bank=_as_int(value("bank")),
        alarm=None,
    )


def _normalise_snmp_value(value: Any) -> Any | None:
    if value is None or value.__class__.__name__ in {
        "NoSuchObject",
        "NoSuchInstance",
        "EndOfMibView",
    }:
        return None
    return value


def _as_text(value: Any | None) -> str | None:
    if value is None:
        return None
    try:
        octets = bytes(value.asOctets())
    except AttributeError:
        text = value.prettyPrint() if hasattr(value, "prettyPrint") else str(value)
    else:
        try:
            text = octets.decode("utf-8")
        except UnicodeDecodeError:
            text = value.prettyPrint()
    text = text.replace("\x00", "").strip()
    return text or None


def _as_int(value: Any | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        text = _as_text(value)
        if text is None:
            return None
        try:
            return int(text)
        except ValueError:
            return None


def _as_scaled_number(value: Any | None, divisor: int) -> float | None:
    raw = _as_int(value)
    if raw is None:
        return None
    return raw / divisor


def _as_pending(value: Any | None) -> bool | None:
    raw = _as_int(value)
    if raw is None:
        return None
    return raw == 1


def _apparent_power(current: float | None, voltage: float | None) -> float | None:
    if current is None or voltage is None:
        return None
    return round(current * voltage, 1)


def _normalise_outlet_power(power: int | None, current: float | None) -> int | None:
    if power == 0 and current is not None and current > 0:
        return None
    return power


def _bounded_outlet_count(value: int) -> int:
    return max(1, min(value, MAX_OUTLETS))


def _chunks(values: Iterable[str], size: int) -> Iterable[tuple[str, ...]]:
    iterator = iter(values)
    while chunk := tuple(islice(iterator, size)):
        yield chunk
