"""Writes the checklist that goes with a generated configuration.

A configuration that loads without errors is not yet a working network.
The checklist says what to type on which device and what the output has to
show, so the result can be verified in Packet Tracer or on real hardware.
"""

from __future__ import annotations

from subnetplan.ios.base import PLACEHOLDER
from subnetplan.plan import Plan, SitePlan
from subnetplan.report import short_interface


def _router_checks(plan: Plan, site: SitePlan) -> list[str]:
    name = site.site.router
    links = plan.links_of(site.site.name)
    lan = short_interface(plan.network.hardware.router_lan)
    out = [f"### {name}", ""]

    subinterfaces = ", ".join(f"`{lan}.{vlan.vlan.id}`" for vlan in site.vlans)
    out += [
        "- `show ip interface brief`",
        f"  - {subinterfaces} are `up/up` with the gateway addresses from the plan.",
    ]
    for link in links:
        here = link.end(site.site.name)
        out.append(f"  - `{short_interface(here.interface)}` is `up/up` with {here.address}.")
    if site.site.internet:
        internet = site.site.internet
        out.append(
            f"  - `{short_interface(internet.interface)}` is `up/up` with {internet.address.ip}."
        )

    pools = [vlan for vlan in site.vlans if vlan.dhcp_range]
    if pools:
        names = ", ".join(f"`{vlan.vlan.name.upper()}`" for vlan in pools)
        out += [
            "- `show ip dhcp pool`",
            f"  - Pools {names} exist.",
            "- `show ip dhcp binding` after a client has been connected",
            "  - The client has a lease from the range in the plan.",
        ]

    if links:
        neighbours = ", ".join(
            f"{link.other(site.site.name).site.router} "
            f"({plan.site(link.other(site.site.name).site.name).router_id})"
            for link in links
        )
        out += [
            "- `show ip ospf neighbor`",
            f"  - {len(links)} neighbour(s) in state `FULL`: {neighbours}.",
            "- `show ip route ospf`",
        ]
        others = [other for other in plan.sites if other is not site]
        remote = sum(len(other.vlans) for other in others)
        out.append(f"  - {remote} routes to the VLAN subnets of the other sites.")
        edge = plan.network.edge
        if edge is not None and edge is not site.site:
            out.append("  - A default route marked `O*E2`, learned from the edge router.")

    if site.site.internet:
        out += [
            "- `show ip route static`",
            f"  - `S* 0.0.0.0/0` via {site.site.internet.gateway}.",
            "- `show ip nat translations` while a client pings an outside address",
            f"  - Inside local addresses from {plan.network.block} are translated "
            f"to {site.site.internet.address.ip}.",
        ]
    return out + [""]


def _switch_checks(plan: Plan, site: SitePlan) -> list[str]:
    hardware = plan.network.hardware
    ids = ",".join(str(vlan.vlan.id) for vlan in site.vlans)
    out = [
        f"### {site.site.switch}",
        "",
        "- `show vlan brief`",
        "  - " + ", ".join(f"VLAN {v.vlan.id} `{v.vlan.name}`" for v in site.vlans) + " exist",
        "    and the access ports are in the VLANs listed below.",
        "- `show interfaces trunk`",
        f"  - `{short_interface(hardware.switch_uplink)}` is trunking, "
        f"allowed VLANs `{ids}`"
        + (f", native VLAN {plan.network.native_vlan}." if plan.network.native_vlan else "."),
    ]
    if any(vlan.vlan.port_security is not None for vlan in site.vlans):
        out += [
            "- `show port-security`",
            "  - Every secured port is listed with violation action `Restrict`.",
        ]
    if site.management:
        out += [
            "- `show ip interface brief`",
            f"  - `Vlan{site.management.vlan.id}` is `up/up` with "
            f"{site.management.switch_address}.",
        ]

    rows = []
    next_port = 1
    for vlan in site.vlans:
        if vlan.vlan.ports:
            last = next_port + vlan.vlan.ports - 1
            ports = f"{next_port}" if last == next_port else f"{next_port}-{last}"
            rows.append(
                f"| {short_interface(hardware.switch_access_prefix)}{ports} "
                f"| {vlan.vlan.id} | {vlan.vlan.name} |"
            )
            next_port = last + 1
    if rows:
        out += ["", "| Ports | VLAN | Name |", "| --- | --- | --- |", *rows]
    return out + [""]


def _ping_tests(plan: Plan) -> list[str]:
    out = ["## End-to-end tests", ""]
    hosts = [(site, vlan) for site in plan.sites for vlan in site.vlans if vlan.dhcp_range]
    if not hosts:
        hosts = [(site, site.vlans[0]) for site in plan.sites]

    first_site, first_vlan = hosts[0]
    out.append(
        f"Connect a PC to an access port of VLAN {first_vlan.vlan.id} "
        f"({first_vlan.vlan.name}) at site {first_site.site.name}. From that PC:"
    )
    out.append("")
    out.append(f"1. `ping {first_vlan.gateway}` reaches its own gateway.")
    step = 2
    for vlan in first_site.vlans:
        if vlan is not first_vlan:
            out.append(
                f"{step}. `ping {vlan.gateway}` reaches VLAN {vlan.vlan.id} "
                "(routing between VLANs)."
            )
            step += 1
    for site in plan.sites:
        if site is not first_site:
            out.append(
                f"{step}. `ping {site.vlans[0].gateway}` reaches site {site.site.name} "
                "(OSPF across the WAN)."
            )
            step += 1
    edge = plan.network.edge
    if edge is not None:
        out.append(
            f"{step}. `ping {edge.internet.gateway}` reaches the provider (default route and NAT)."
        )
        step += 1
    if len(plan.links) > len(plan.sites) - 1:
        out += [
            "",
            "The WAN has more links than it needs to connect all sites. Shut down one WAN "
            "interface, wait for OSPF to converge and repeat the pings between sites: they "
            "must still succeed over the remaining links.",
        ]
    return out + [""]


def render_checklist(plan: Plan) -> str:
    network = plan.network
    out = [
        f"# Verification checklist: {network.name}",
        "",
        "## Before you start",
        "",
        f"1. Replace every `{PLACEHOLDER}` in the configuration files with real secrets.",
        "2. Generate the SSH host key on every device. It is not part of the configuration file:",
        "   `crypto key generate rsa general-keys modulus 2048`",
    ]
    serial = [link for link in plan.links if link.a.interface.startswith("Serial")]
    if serial:
        ends = ", ".join(f"{link.a.site.router} - {link.b.site.router}" for link in serial)
        out.append(
            f"3. Serial links ({ends}): set `clock rate 128000` on the interface "
            "that has the DCE end of the cable."
        )
    out += ["", "## Per device", ""]
    for site in plan.sites:
        out += _router_checks(plan, site)
        out += _switch_checks(plan, site)
    out += _ping_tests(plan)
    return "\n".join(out)
