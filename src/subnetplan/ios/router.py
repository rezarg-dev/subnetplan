"""The LAN side of a site router: router-on-a-stick and DHCP."""

from __future__ import annotations

from subnetplan.model import Network
from subnetplan.plan import SitePlan


def lan_interfaces(site: SitePlan, network: Network, nat_inside: bool = False) -> list[str]:
    """One subinterface per VLAN on the trunk to the switch.

    `nat_inside` marks the subinterfaces as the inside of NAT, which only
    the router with the internet uplink needs.
    """
    lan = network.hardware.router_lan
    lines = [
        f"interface {lan}",
        f" description Trunk to {site.site.switch}",
        " no ip address",
        " no shutdown",
    ]

    for vlan in site.vlans:
        lines += [
            "!",
            f"interface {lan}.{vlan.vlan.id}",
            f" description {vlan.vlan.name}",
            f" encapsulation dot1Q {vlan.vlan.id}",
            f" ip address {vlan.gateway} {vlan.network.netmask}",
        ]
        if nat_inside:
            lines.append(" ip nat inside")

    if network.native_vlan is not None:
        # Tells the router which VLAN arrives untagged, so both ends of the
        # trunk agree on the native VLAN.
        lines += [
            "!",
            f"interface {lan}.{network.native_vlan}",
            " description native VLAN, no hosts",
            f" encapsulation dot1Q {network.native_vlan} native",
        ]
    return lines


def dhcp(site: SitePlan, network: Network) -> list[str]:
    """A DHCP pool for every VLAN that wants one."""
    pools = [vlan for vlan in site.vlans if vlan.dhcp_range]
    if not pools:
        return []

    # Excluded addresses are global commands and have to come before the
    # pools, otherwise the router may lease the gateway address to a client
    # in the moment between the two commands.
    lines = [f"ip dhcp excluded-address {vlan.gateway}" for vlan in pools]

    for vlan in pools:
        lines += [
            "!",
            f"ip dhcp pool {vlan.vlan.name.upper()}",
            f" network {vlan.network.network_address} {vlan.network.netmask}",
            f" default-router {vlan.gateway}",
        ]
        if network.dns_servers:
            servers = " ".join(str(server) for server in network.dns_servers)
            lines.append(f" dns-server {servers}")
        lines.append(f" domain-name {network.domain}")
    return lines
