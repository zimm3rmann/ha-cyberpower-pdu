# CyberPower PDU

Home Assistant custom integration for CyberPower switched PDUs, tested with the CyberPower PDU41001.

![CyberPower PDU logo](custom_components/cyberpower_pdu/brand/logo.png)

## Features

- PDU-level sensors for active power, apparent power, current, voltage, and energy.
- One switch entity per outlet for on/off control.
- One disabled-by-default power-cycle button per outlet.
- SNMPv2c and SNMPv3 support.
- Config flow setup from the Home Assistant UI.

Per-outlet power sensors are intentionally not created. The tested PDU41001 firmware exposed unreliable per-outlet power readings on some outlets, while the overall PDU metrics were consistent.

## Installation

### HACS

1. Open HACS.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add this repository URL as an **Integration** repository.
4. Download **CyberPower PDU** from HACS.
5. Restart Home Assistant.
6. Go to **Settings > Devices & services > Add integration** and add **CyberPower PDU**.

### Manual

1. Copy `custom_components/cyberpower_pdu` into your Home Assistant config directory at `/config/custom_components/cyberpower_pdu`.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration** and add **CyberPower PDU**.

## Configuration

Enable SNMP on the PDU before adding the integration. Outlet controls and power cycling require SNMP write access.

SNMPv2c is the simplest option for the PDU41001 and is the default in the setup flow. SNMPv3 is available when the PDU has a configured SNMPv3 user with the required authentication and privacy settings.

The setup flow asks for:

- Hostname or IP address.
- SNMP port, usually `161`.
- SNMP version.
- Community string for SNMPv2c, or username/auth/privacy credentials for SNMPv3.

## Entities

The integration creates one Home Assistant device for the PDU.

Enabled by default:

- `sensor`: PDU active power.
- `sensor`: PDU apparent power.
- `sensor`: PDU current.
- `sensor`: PDU voltage.
- `sensor`: PDU energy.
- `switch`: One switch per outlet.

Disabled by default:

- `button`: One power-cycle button per outlet.

Enable the outlet power-cycle buttons you want from each entity's settings in Home Assistant.

## Troubleshooting

`No SNMP response received before timeout` usually means Home Assistant cannot query the PDU. Check that SNMP is enabled, the host and port are correct, the credentials have read access, and the PDU allows the Home Assistant host as an SNMP manager.

If outlet switches click relays but do not immediately show the expected state, wait for the next coordinator refresh and confirm the SNMP user or community has write access. The integration polls the PDU in small batches because the tested firmware can time out when too many OIDs are requested at once.

You can also probe SNMP directly from this repository:

```bash
python3 tools/snmp_probe.py --host PDU_IP --version v2c --community COMMUNITY
python3 tools/snmp_probe.py --host PDU_IP --version v3 --username USER --auth-key AUTH_KEY --privacy-key PRIVACY_KEY
```

## Development

Run a syntax check before packaging changes:

```bash
python3 -m compileall custom_components tools
```

## Attribution

The brand image is derived from the CyberPower icon in Homarr Labs Dashboard Icons, licensed under Apache-2.0. CyberPower is a trademark of Cyber Power Systems, Inc. This project is not affiliated with or endorsed by Cyber Power Systems, Inc.

## License

MIT
