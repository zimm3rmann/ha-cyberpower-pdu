# CyberPower PDU41001 Home Assistant Integration

This custom integration talks to the PDU over SNMP. SNMPv2c is the default for broad compatibility with this model. SNMPv3 should be used instead when the PDU has a configured read/write SNMPv3 user.

## Install

This is a Home Assistant custom integration, not a Supervisor add-on. Install it into the Home Assistant config directory under `custom_components/`.

For HAOS, the direct install path is:

1. Install an HAOS file-access method such as Studio Code Server, File editor, SSH, or Samba.
2. Create `/config/custom_components/` if it does not already exist.
3. Copy this repository's `custom_components/cyberpower_pdu` directory to `/config/custom_components/cyberpower_pdu`.
4. Restart Home Assistant.
5. Add the integration from Settings > Devices & services > Add integration > CyberPower PDU.

After this project is pushed to GitHub, HACS can install it as a custom integration repository:

1. Open HACS.
2. Open the three-dot menu and choose Custom repositories.
3. Paste the GitHub repository URL.
4. Choose Integration as the repository type.
5. Download it, restart Home Assistant, then add CyberPower PDU from Settings > Devices & services.

Enter the PDU hostname or IP address in the config flow.

The SNMP credentials need read/write access for outlet on/off and power-cycle commands.

The tested firmware times out when too many OIDs are requested in one SNMP packet, so the integration intentionally polls in small groups.

## Local Test Container

A throwaway Home Assistant Container instance can be used to test the integration before installing it on HAOS.

The current local test instance is running at:

```text
http://127.0.0.1:8124/
```

It uses `/tmp/ha_pdu_config` as the Home Assistant config directory and bind-mounts this repo's integration directory into `/config/custom_components/cyberpower_pdu`.

Useful commands:

```bash
docker logs -f ha-pdu-test
docker restart ha-pdu-test
docker stop ha-pdu-test
docker rm ha-pdu-test
```

Restart the container after editing Python files so Home Assistant reloads the integration code.

To probe SNMP outside the UI, run the helper from a Python environment that has PySNMP installed:

```bash
python3 tools/snmp_probe.py --host PDU_IP --version v2c --community COMMUNITY
python3 tools/snmp_probe.py --host PDU_IP --version v3 --username USER --auth-key AUTH --privacy-key PRIVACY
```

If this reports `No SNMP response received before timeout`, verify SNMP is enabled on the PDU, the user or community has read/write SNMP access, and the PDU's SNMP manager/IP allow list permits the Home Assistant host.

## Entities

The integration creates:

- One switch per outlet for immediate on/off control.
- One disabled-by-default Power Cycle button per outlet. Enable only the outlet cycle buttons you want visible.
- PDU-level sensors for active power, apparent power, current, voltage, and energy.

The tested PDU41001 firmware exposes unreliable per-outlet active power for some outlets, so the integration intentionally does not create per-outlet metric sensors. Outlet state and controls are still per outlet.

## SNMP OIDs

The integration uses the CyberPower CPS-MIB `ePDU` branch:

- Device identity: `.1.3.6.1.4.1.3808.1.1.3.1`
- Total load status: `.1.3.6.1.4.1.3808.1.1.3.2.3.1.1`
- Outlet control: `.1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.<outlet>`
- Outlet status and metering: `.1.3.6.1.4.1.3808.1.1.3.3.5.1.1`

Command values are `1` for immediate on, `2` for immediate off, and `3` for immediate reboot.

It also falls back to the CPS-MIB `ats` outlet branch for CyberPower units that expose outlet switching there:

- ATS device identity: `.1.3.6.1.4.1.3808.1.1.5.1`
- ATS outlet status: `.1.3.6.1.4.1.3808.1.1.5.6.3.1`
- ATS outlet control: `.1.3.6.1.4.1.3808.1.1.5.6.5.1.3.<outlet>`

The ATS fallback is used only for outlet state and controls.

References checked:

- CyberPower PDU41001 product page: https://www.cyberpowersystems.com/product/pdus/switched/pdu41001/
- CPS-MIB browser: https://mibs.observium.org/mib/CPS-MIB/
