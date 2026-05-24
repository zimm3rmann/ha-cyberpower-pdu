from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    AUTH_NONE,
    AUTH_PROTOCOLS,
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_COMMUNITY,
    CONF_CONTEXT_NAME,
    CONF_PRIVACY_KEY,
    CONF_PRIVACY_PROTOCOL,
    CONF_RETRIES,
    CONF_SNMP_VERSION,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_PRIVACY_PROTOCOL,
    DEFAULT_RETRIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SNMP_VERSION,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PRIVACY_NONE,
    PRIVACY_PROTOCOLS,
    SNMP_V3,
    SNMP_VERSIONS,
)
from .snmp import (
    CyberPowerPduClient,
    CyberPowerPduConfig,
    CyberPowerPduConnectionError,
    CyberPowerPduDevice,
    CyberPowerPduError,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(Exception):
    pass


class InvalidInput(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class CyberPowerPduConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._base_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._base_config = dict(user_input)
            if user_input[CONF_SNMP_VERSION] == SNMP_V3:
                return await self.async_step_v3()
            return await self.async_step_community()

        return self.async_show_form(step_id="user", data_schema=_user_schema())

    async def async_step_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            config = {**self._base_config, **user_input}
            try:
                device = await _validate_config(config)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidInput as err:
                errors["base"] = err.reason
            else:
                return await self._create_entry(config, device)

        return self.async_show_form(step_id="v3", data_schema=_v3_schema(), errors=errors)

    async def async_step_community(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            config = {**self._base_config, **user_input}
            try:
                device = await _validate_config(config)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidInput as err:
                errors["base"] = err.reason
            else:
                return await self._create_entry(config, device)

        return self.async_show_form(
            step_id="community",
            data_schema=_community_schema(),
            errors=errors,
        )

    async def _create_entry(
        self, config: dict[str, Any], device: CyberPowerPduDevice
    ) -> config_entries.ConfigFlowResult:
        identifier = device.serial or f"{config[CONF_HOST]}:{config[CONF_PORT]}"
        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured(updates={CONF_HOST: config[CONF_HOST]})
        title = device.name or device.model or f"CyberPower PDU {config[CONF_HOST]}"
        return self.async_create_entry(title=title, data=config)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> CyberPowerPduOptionsFlowHandler:
        return CyberPowerPduOptionsFlowHandler(config_entry)


class CyberPowerPduOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=5, max=3600)
                    )
                }
            ),
        )


async def _validate_config(config: dict[str, Any]) -> CyberPowerPduDevice:
    _validate_credentials(config)
    client = CyberPowerPduClient(_client_config(config))
    try:
        device = await client.async_fetch_device_info()
    except (CyberPowerPduConnectionError, CyberPowerPduError) as err:
        _LOGGER.warning("CyberPower PDU SNMP validation failed: %s", err)
        raise CannotConnect from err
    finally:
        await client.async_close()

    if not any(
        (device.name, device.model, device.serial, device.outlet_count, device.controlled_outlets)
    ):
        raise CannotConnect
    return device


def _validate_credentials(config: dict[str, Any]) -> None:
    if config[CONF_SNMP_VERSION] != SNMP_V3:
        if not config.get(CONF_COMMUNITY):
            raise InvalidInput("missing_community")
        return

    if not config.get(CONF_USERNAME):
        raise InvalidInput("missing_username")

    auth_protocol = config[CONF_AUTH_PROTOCOL]
    auth_key = config.get(CONF_AUTH_KEY) or ""
    privacy_protocol = config[CONF_PRIVACY_PROTOCOL]
    privacy_key = config.get(CONF_PRIVACY_KEY) or ""

    if auth_protocol != AUTH_NONE and not 8 <= len(auth_key) <= 32:
        raise InvalidInput("auth_key_length")
    if privacy_protocol != PRIVACY_NONE and auth_protocol == AUTH_NONE:
        raise InvalidInput("privacy_requires_auth")
    if privacy_protocol != PRIVACY_NONE and not 8 <= len(privacy_key) <= 32:
        raise InvalidInput("privacy_key_length")


def _client_config(config: dict[str, Any]) -> CyberPowerPduConfig:
    return CyberPowerPduConfig(
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        version=config[CONF_SNMP_VERSION],
        community=config.get(CONF_COMMUNITY),
        username=config.get(CONF_USERNAME),
        auth_protocol=config.get(CONF_AUTH_PROTOCOL, DEFAULT_AUTH_PROTOCOL),
        auth_key=config.get(CONF_AUTH_KEY),
        privacy_protocol=config.get(CONF_PRIVACY_PROTOCOL, DEFAULT_PRIVACY_PROTOCOL),
        privacy_key=config.get(CONF_PRIVACY_KEY),
        context_name=config.get(CONF_CONTEXT_NAME, ""),
        timeout=float(config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
        retries=int(config.get(CONF_RETRIES, DEFAULT_RETRIES)),
    )


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_SNMP_VERSION, default=DEFAULT_SNMP_VERSION): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(SNMP_VERSIONS),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _v3_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_AUTH_PROTOCOL, default=DEFAULT_AUTH_PROTOCOL): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(AUTH_PROTOCOLS),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_AUTH_KEY, default=""): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_PRIVACY_PROTOCOL,
                default=DEFAULT_PRIVACY_PROTOCOL,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(PRIVACY_PROTOCOLS),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_PRIVACY_KEY, default=""): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_CONTEXT_NAME, default=""): str,
            vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
                vol.Coerce(float), vol.Range(min=0.5, max=30)
            ),
            vol.Required(CONF_RETRIES, default=DEFAULT_RETRIES): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
            vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=3600)
            ),
        }
    )


def _community_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
            vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
                vol.Coerce(float), vol.Range(min=0.5, max=30)
            ),
            vol.Required(CONF_RETRIES, default=DEFAULT_RETRIES): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
            vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=3600)
            ),
        }
    )
