"""The plan as a graph of devices and cables, for drawing a network diagram."""

from __future__ import annotations

from typing import Any

from subnetplan.plan import Plan


def to_topology(plan: Plan) -> dict[str, Any]:
    """Nodes and links in the shape graph libraries expect.

    Every node has a unique `id`, every link refers to two node ids as
    `source` and `target`.
    """
    hardware = plan.network.hardware
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    for site in plan.sites:
        nodes.append(
            {
                "id": site.site.router,
                "kind": "router",
                "site": site.site.name,
                "router_id": str(site.router_id),
                "summary": str(site.summary),
            }
        )
        nodes.append(
            {
                "id": site.site.switch,
                "kind": "switch",
                "site": site.site.name,
                "management_address": (
                    str(site.management.switch_address) if site.management else None
                ),
                "vlans": [
                    {"id": vlan.vlan.id, "name": vlan.vlan.name, "network": str(vlan.network)}
                    for vlan in site.vlans
                ],
            }
        )
        links.append(
            {
                "source": site.site.router,
                "target": site.site.switch,
                "kind": "trunk",
                "source_interface": hardware.router_lan,
                "target_interface": hardware.switch_uplink,
                "vlans": [vlan.vlan.id for vlan in site.vlans],
            }
        )

    for link in plan.links:
        links.append(
            {
                "source": link.a.site.router,
                "target": link.b.site.router,
                "kind": "wan",
                "network": str(link.network),
                "source_interface": link.a.interface,
                "target_interface": link.b.interface,
                "source_address": str(link.a.address),
                "target_address": str(link.b.address),
            }
        )

    edge = plan.network.edge
    if edge is not None:
        nodes.append({"id": "internet", "kind": "cloud"})
        links.append(
            {
                "source": edge.router,
                "target": "internet",
                "kind": "uplink",
                "network": str(edge.internet.address.network),
                "source_interface": edge.internet.interface,
                "source_address": str(edge.internet.address.ip),
                "target_address": str(edge.internet.gateway),
            }
        )

    return {"name": plan.network.name, "nodes": nodes, "links": links}
