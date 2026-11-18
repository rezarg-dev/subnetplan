"""The access switch of a site."""

from __future__ import annotations

from subnetplan.model import Network
from subnetplan.plan import SitePlan


def port_range(prefix: str, first: int, last: int) -> str:
    """The `interface` command for ports first..last, e.g. FastEthernet0/1 - 12."""
    if first == last:
        return f"interface {prefix}{first}"
    return f"interface range {prefix}{first} - {last}"


def vlans(site: SitePlan, network: Network) -> list[str]:
    lines = []
    for vlan in site.vlans:
        lines += [f"vlan {vlan.vlan.id}", f" name {vlan.vlan.name}"]
    if network.native_vlan is not None:
        lines += [f"vlan {network.native_vlan}", " name native"]
    return lines


def uplink(site: SitePlan, network: Network) -> list[str]:
    allowed = ",".join(str(vlan.vlan.id) for vlan in site.vlans)
    lines = [
        f"interface {network.hardware.switch_uplink}",
        f" description Trunk to {site.site.router}",
        " switchport mode trunk",
    ]
    if network.native_vlan is not None:
        lines.append(f" switchport trunk native vlan {network.native_vlan}")
    lines += [
        # Only the VLANs of this site may cross the trunk.
        f" switchport trunk allowed vlan {allowed}",
        # A fixed trunk has no reason to negotiate.
        " switchport nonegotiate",
    ]
    return lines


def access_ports(site: SitePlan, network: Network) -> list[str]:
    """Access ports, handed out from port 1 upwards in VLAN order.

    Ports left over at the end are shut down.
    """
    hardware = network.hardware
    prefix = hardware.switch_access_prefix
    lines: list[str] = []
    next_port = 1

    for vlan in site.vlans:
        count = vlan.vlan.ports
        if count == 0:
            continue
        if lines:
            lines.append("!")
        lines += [
            port_range(prefix, next_port, next_port + count - 1),
            f" description {vlan.vlan.name}",
            " switchport mode access",
            f" switchport access vlan {vlan.vlan.id}",
        ]
        if vlan.vlan.port_security is not None:
            lines += [
                " switchport port-security",
                f" switchport port-security maximum {vlan.vlan.port_security}",
                # Learn the first devices that connect and keep them.
                " switchport port-security mac-address sticky",
                # Drop frames from unknown devices and log it, but keep the
                # port up for the known ones.
                " switchport port-security violation restrict",
            ]
        lines += [
            # End devices cannot cause loops, so the port may forward at once.
            " spanning-tree portfast",
            # If a switch is plugged in anyway, shut the port down.
            " spanning-tree bpduguard enable",
        ]
        next_port += count

    if next_port <= hardware.switch_access_ports:
        if lines:
            lines.append("!")
        lines += [
            port_range(prefix, next_port, hardware.switch_access_ports),
            " description unused",
            " shutdown",
        ]
    for name in hardware.switch_spare:
        lines += ["!", f"interface {name}", " description unused", " shutdown"]
    return lines


def management(site: SitePlan) -> list[str]:
    """The switch's own address, for SSH. Empty without a management VLAN."""
    vlan = site.management
    if vlan is None:
        return []
    return [
        f"interface Vlan{vlan.vlan.id}",
        f" description {vlan.vlan.name}",
        f" ip address {vlan.switch_address} {vlan.network.netmask}",
        " no shutdown",
        "!",
        # A layer 2 switch does not route. It needs this to answer
        # management traffic that comes from another subnet.
        f"ip default-gateway {vlan.gateway}",
    ]
