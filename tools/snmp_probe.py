from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, "/config")

from custom_components.cyberpower_pdu.const import (
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_PRIVACY_PROTOCOL,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    SNMP_V2C,
    SNMP_V3,
)
from custom_components.cyberpower_pdu.snmp import CyberPowerPduClient, CyberPowerPduConfig


async def _probe(args: argparse.Namespace) -> None:
    client = CyberPowerPduClient(
        CyberPowerPduConfig(
            host=args.host,
            port=args.port,
            version=args.version,
            community=args.community,
            username=args.username,
            auth_protocol=args.auth_protocol,
            auth_key=args.auth_key,
            privacy_protocol=args.privacy_protocol,
            privacy_key=args.privacy_key,
            context_name=args.context_name,
            timeout=args.timeout,
            retries=args.retries,
        )
    )
    try:
        if args.oid:
            async with client._lock:
                values = await client._get_many_locked(args.oid)
            for oid, value in values.items():
                print(f"{oid}={value.prettyPrint() if hasattr(value, 'prettyPrint') else value}")
            return

        device = await client.async_fetch_device_info()
        print(f"branch={device.mib_branch}")
        print(f"name={device.name}")
        print(f"model={device.model}")
        print(f"serial={device.serial}")
        print(f"outlets={device.controlled_outlets or device.outlet_count}")
        if args.device_only:
            return

        data = await client.async_fetch()
        print(f"total_power={data.power}")
        for outlet in data.outlets:
            print(
                f"outlet={outlet.index} name={outlet.name!r} state={outlet.state} "
                f"active_power={outlet.power} apparent_power={outlet.apparent_power} "
                f"current={outlet.current}"
            )
    finally:
        await client.async_close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--version", choices=("v1", "v2c", "v3"), default=SNMP_V3)
    parser.add_argument("--community", default=DEFAULT_COMMUNITY)
    parser.add_argument("--username")
    parser.add_argument("--auth-protocol", default=DEFAULT_AUTH_PROTOCOL)
    parser.add_argument("--auth-key")
    parser.add_argument("--privacy-protocol", default=DEFAULT_PRIVACY_PROTOCOL)
    parser.add_argument("--privacy-key")
    parser.add_argument("--context-name", default="")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--device-only", action="store_true")
    parser.add_argument("--oid", action="append")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.version != SNMP_V3:
        args.username = None
        args.auth_key = None
        args.privacy_key = None
    if args.version == SNMP_V2C and not args.community:
        args.community = DEFAULT_COMMUNITY
    asyncio.run(_probe(args))


if __name__ == "__main__":
    main()
