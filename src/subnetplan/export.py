"""Machine-readable and document formats of a plan: JSON, CSV and Markdown."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from subnetplan.plan import Plan


def to_dict(plan: Plan) -> dict[str, Any]:
    network = plan.network
    return {
        "name": network.name,
        "block": str(network.block),
        "sites": [
            {
                "name": site.site.name,
                "summary": str(site.summary),
                "router": {"hostname": site.site.router, "router_id": str(site.router_id)},
                "switch": {
                    "hostname": site.site.switch,
                    "management_address": (
                        str(site.management.switch_address) if site.management else None
                    ),
                },
                "vlans": [
                    {
                        "id": vlan.vlan.id,
                        "name": vlan.vlan.name,
                        "hosts": vlan.vlan.hosts,
                        "network": str(vlan.network),
                        "netmask": str(vlan.network.netmask),
                        "gateway": str(vlan.gateway),
                        "usable": vlan.usable,
                        "dhcp_range": (
                            [str(vlan.dhcp_range[0]), str(vlan.dhcp_range[1])]
                            if vlan.dhcp_range
                            else None
                        ),
                    }
                    for vlan in site.vlans
                ],
            }
            for site in plan.sites
        ],
        "links": [
            {
                "network": str(link.network),
                "ends": [
                    {
                        "site": end.site.name,
                        "router": end.site.router,
                        "interface": end.interface,
                        "address": str(end.address),
                    }
                    for end in (link.a, link.b)
                ],
            }
            for link in plan.links
        ],
        "wan_block": str(plan.wan_block) if plan.wan_block else None,
        "free": [str(block) for block in plan.free],
        "hosts_requested": plan.hosts_requested,
        "addresses_allocated": plan.addresses_allocated,
    }


def to_json(plan: Plan) -> str:
    return json.dumps(to_dict(plan), indent=2) + "\n"


def to_csv(plan: Plan) -> str:
    """One row per subnet, ready for a spreadsheet or an IPAM import."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["site", "kind", "vlan", "name", "network", "netmask", "gateway", "dhcp_first", "dhcp_last"]
    )
    for site in plan.sites:
        for vlan in site.vlans:
            first, last = vlan.dhcp_range or ("", "")
            writer.writerow(
                [
                    site.site.name,
                    "vlan",
                    vlan.vlan.id,
                    vlan.vlan.name,
                    vlan.network,
                    vlan.network.netmask,
                    vlan.gateway,
                    first,
                    last,
                ]
            )
    for link in plan.links:
        name = f"{link.a.site.name}-{link.b.site.name}"
        writer.writerow(["", "link", "", name, link.network, link.network.netmask, "", "", ""])
    return buffer.getvalue()


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def to_markdown(plan: Plan) -> str:
    network = plan.network
    out = [f"# Addressing plan: {network.name}", "", f"Block: `{network.block}`", ""]

    for site in plan.sites:
        out += [
            f"## Site {site.site.name}",
            "",
            f"Summary route `{site.summary}`, router `{site.site.router}` "
            f"(router id {site.router_id}), switch `{site.site.switch}`.",
            "",
        ]
        rows = []
        for vlan in site.vlans:
            dhcp = "static"
            if vlan.dhcp_range:
                dhcp = f"{vlan.dhcp_range[0]} to {vlan.dhcp_range[1]}"
            rows.append(
                [
                    str(vlan.vlan.id),
                    vlan.vlan.name,
                    str(vlan.vlan.hosts),
                    f"`{vlan.network}`",
                    str(vlan.network.netmask),
                    str(vlan.gateway),
                    dhcp,
                ]
            )
        out += _markdown_table(["VLAN", "Name", "Hosts", "Subnet", "Mask", "Gateway", "DHCP"], rows)
        out.append("")

    if plan.links:
        out += ["## WAN links", "", f"Taken from `{plan.wan_block}`.", ""]
        rows = [
            [
                f"{link.a.site.name} to {link.b.site.name}",
                f"`{link.network}`",
                f"{link.a.site.router} {link.a.interface} {link.a.address}",
                f"{link.b.site.router} {link.b.interface} {link.b.address}",
            ]
            for link in plan.links
        ]
        out += _markdown_table(["Link", "Subnet", "Side A", "Side B"], rows)
        out.append("")

    free = ", ".join(f"`{block}`" for block in plan.free) or "none"
    out += ["## Free space", "", free, ""]
    return "\n".join(out)
