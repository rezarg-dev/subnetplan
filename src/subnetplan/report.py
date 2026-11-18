"""Human-readable rendering of a plan for the terminal."""

from __future__ import annotations

from subnetplan.plan import Plan


def table(headers: list[str], rows: list[list[str]], indent: str = "  ") -> list[str]:
    """Left-aligned columns, each as wide as its longest cell."""
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells: list[str]) -> str:
        padded = (cell.ljust(width) for cell, width in zip(cells, widths, strict=True))
        return (indent + "  ".join(padded)).rstrip()

    return [line(headers), line(["-" * width for width in widths]), *(line(row) for row in rows)]


def short_interface(name: str) -> str:
    """GigabitEthernet0/1 -> Gi0/1, the way IOS abbreviates it in show commands."""
    for long, short in (("GigabitEthernet", "Gi"), ("FastEthernet", "Fa"), ("Serial", "Se")):
        if name.startswith(long):
            return short + name[len(long) :]
    return name


def render_plan(plan: Plan) -> str:
    network = plan.network
    out = [f"Network {network.name}   block {network.block}", ""]

    for site in plan.sites:
        out.append(
            f"Site {site.site.name}   summary {site.summary}   "
            f"router {site.site.router} (id {site.router_id})   switch {site.site.switch}"
        )
        rows = []
        for vlan in site.vlans:
            dhcp = "-"
            if vlan.dhcp_range:
                dhcp = f"{vlan.dhcp_range[0]} - {vlan.dhcp_range[1]}"
            rows.append(
                [
                    str(vlan.vlan.id),
                    vlan.vlan.name,
                    str(vlan.vlan.hosts),
                    str(vlan.network),
                    str(vlan.network.netmask),
                    str(vlan.gateway),
                    dhcp,
                    str(vlan.usable),
                ]
            )
        out += table(
            ["VLAN", "Name", "Hosts", "Subnet", "Mask", "Gateway", "DHCP range", "Usable"], rows
        )
        out.append("")

    if plan.links:
        out.append(f"WAN links   block {plan.wan_block}")
        rows = [
            [
                f"{link.a.site.name} - {link.b.site.name}",
                str(link.network),
                f"{link.a.site.router} {short_interface(link.a.interface)} {link.a.address}",
                f"{link.b.site.router} {short_interface(link.b.interface)} {link.b.address}",
            ]
            for link in plan.links
        ]
        out += table(["Link", "Subnet", "Side A", "Side B"], rows)
        out.append("")

    total = network.block.num_addresses
    allocated = plan.addresses_allocated
    free = ", ".join(str(block) for block in plan.free) or "none"
    out += [
        "Summary",
        f"  Hosts requested      {plan.hosts_requested}",
        f"  Addresses allocated  {allocated} of {total} ({allocated / total:.0%})",
        f"  Free blocks          {free}",
    ]
    return "\n".join(out) + "\n"
