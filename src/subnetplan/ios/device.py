"""Puts the sections together into one configuration per device."""

from __future__ import annotations

from subnetplan.ios import base, edge, router, routing, switch
from subnetplan.plan import Plan, SitePlan


def _join(sections: list[list[str]]) -> str:
    """Sections separated by a "!" line, empty sections left out."""
    lines: list[str] = []
    for section in sections:
        if not section:
            continue
        if lines:
            lines.append("!")
        lines += section
    return "\n".join([*lines, "!", "end"]) + "\n"


def render_router(plan: Plan, site: SitePlan) -> str:
    network = plan.network
    is_edge = site.site.internet is not None
    return _join(
        [
            base.header(site.site.router, network),
            base.identity(site.site.router, network),
            router.dhcp(site, network),
            router.lan_interfaces(site, network, nat_inside=is_edge),
            routing.wan_interfaces(plan, site, nat_inside=is_edge),
            edge.uplink(site),
            routing.ospf(plan, site),
            edge.nat(plan, site),
            base.access(vty_last=4),
        ]
    )


def render_switch(plan: Plan, site: SitePlan) -> str:
    network = plan.network
    return _join(
        [
            base.header(site.site.switch, network),
            base.identity(site.site.switch, network),
            switch.vlans(site, network),
            switch.uplink(site, network),
            switch.access_ports(site, network),
            switch.management(site),
            base.access(vty_last=15),
        ]
    )


def render_all(plan: Plan) -> dict[str, str]:
    """File name -> configuration, for every device in the plan."""
    files = {}
    for site in plan.sites:
        files[f"{site.site.router}.cfg"] = render_router(plan, site)
        files[f"{site.site.switch}.cfg"] = render_switch(plan, site)
    return files
