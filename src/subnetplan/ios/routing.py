"""The WAN side of a site router: point-to-point links and OSPF."""

from __future__ import annotations

from subnetplan.plan import Plan, SitePlan


def wan_interfaces(plan: Plan, site: SitePlan, nat_inside: bool = False) -> list[str]:
    lines: list[str] = []
    for link in plan.links_of(site.site.name):
        here, there = link.end(site.site.name), link.other(site.site.name)
        if lines:
            lines.append("!")
        lines += [
            f"interface {here.interface}",
            f" description Link to {there.site.router}",
            f" ip address {here.address} {link.network.netmask}",
        ]
        if nat_inside:
            # Traffic from the other sites enters the edge router here.
            lines.append(" ip nat inside")
        lines.append(" no shutdown")
    return lines


def ospf(plan: Plan, site: SitePlan) -> list[str]:
    """Single-area OSPF. Empty for a network without WAN links."""
    links = plan.links_of(site.site.name)
    if not links:
        return []

    lines = [
        "router ospf 1",
        f" router-id {site.router_id}",
        # No OSPF neighbours can exist on the user VLANs. Sending hellos
        # there would only invite someone to inject routes.
        " passive-interface default",
    ]
    lines += [f" no passive-interface {link.end(site.site.name).interface}" for link in links]

    # OSPF network statements take a wildcard mask, the inverse of the
    # subnet mask.
    networks = [vlan.network for vlan in site.vlans] + [link.network for link in links]
    lines += [
        f" network {network.network_address} {network.hostmask} area 0"
        for network in sorted(networks)
    ]

    if site.site.internet is not None:
        # Announce the default route to the other sites.
        lines.append(" default-information originate")
    return lines
