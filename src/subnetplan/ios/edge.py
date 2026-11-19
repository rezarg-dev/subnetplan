"""Internet access on the edge router: uplink, default route and NAT."""

from __future__ import annotations

from subnetplan.plan import Plan, SitePlan

_NAT_ACL = 1


def uplink(site: SitePlan) -> list[str]:
    internet = site.site.internet
    if internet is None:
        return []
    return [
        f"interface {internet.interface}",
        " description Internet uplink",
        f" ip address {internet.address.ip} {internet.address.network.netmask}",
        " ip nat outside",
        " no shutdown",
    ]


def nat(plan: Plan, site: SitePlan) -> list[str]:
    """Default route and port address translation for the whole network."""
    internet = site.site.internet
    if internet is None:
        return []
    block = plan.network.block
    return [
        f"ip route 0.0.0.0 0.0.0.0 {internet.gateway}",
        "!",
        # One entry covers every site, because all of them were allocated
        # from the same block.
        f"access-list {_NAT_ACL} permit {block.network_address} {block.hostmask}",
        # "overload" lets all inside hosts share the uplink address,
        # told apart by their source ports.
        f"ip nat inside source list {_NAT_ACL} interface {internet.interface} overload",
    ]
