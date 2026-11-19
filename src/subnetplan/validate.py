"""Checks that a network description makes sense before anything is planned."""

from __future__ import annotations

import re

from subnetplan.interfaces import InterfaceError, assign_link_interfaces
from subnetplan.loader import ConfigError
from subnetplan.model import Network, Site

_NAME = re.compile(r"^[a-z][a-z0-9-]{0,19}$")

# 1 is the default VLAN and 1002-1005 are reserved for Token Ring and FDDI
# on Cisco switches; they cannot be created or deleted.
_RESERVED_VLANS = {1, 1002, 1003, 1004, 1005}


def _check_vlan_id(vlan_id: int, where: str, problems: list[str]) -> None:
    if not 1 <= vlan_id <= 4094:
        problems.append(f"{where}: VLAN id {vlan_id} is outside 1-4094")
    elif vlan_id in _RESERVED_VLANS:
        problems.append(f"{where}: VLAN {vlan_id} is reserved on Cisco switches")


def _check_site(network: Network, site: Site, where: str, problems: list[str]) -> None:
    if not _NAME.match(site.name):
        problems.append(
            f"{where}.name: {site.name!r} must start with a letter and contain only "
            "lower-case letters, digits and hyphens (at most 20 characters)"
        )
    if not site.vlans:
        problems.append(f"{where}: a site needs at least one VLAN")

    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    for index, vlan in enumerate(site.vlans):
        vlan_where = f"{where}.vlans[{index}]"
        _check_vlan_id(vlan.id, f"{vlan_where}.id", problems)
        if vlan.id in seen_ids:
            problems.append(f"{vlan_where}.id: VLAN {vlan.id} is used twice in site {site.name}")
        seen_ids.add(vlan.id)
        if vlan.id == network.native_vlan:
            problems.append(
                f"{vlan_where}.id: VLAN {vlan.id} is the native VLAN and cannot carry hosts"
            )

        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", vlan.name):
            problems.append(
                f"{vlan_where}.name: {vlan.name!r} must be 1-32 letters, digits, "
                "hyphens or underscores"
            )
        if vlan.name.lower() in seen_names:
            problems.append(f"{vlan_where}.name: {vlan.name!r} is used twice in site {site.name}")
        seen_names.add(vlan.name.lower())

        if vlan.hosts < 1:
            problems.append(f"{vlan_where}.hosts: must be at least 1")
        if vlan.ports < 0:
            problems.append(f"{vlan_where}.ports: cannot be negative")
        if vlan.port_security is not None and not 1 <= vlan.port_security <= 132:
            # 132 is the upper bound a Catalyst 2960 accepts.
            problems.append(f"{vlan_where}.port_security: must be between 1 and 132")
        if vlan.management and vlan.dhcp:
            problems.append(
                f"{vlan_where}: a management VLAN holds statically addressed devices, "
                "set dhcp = false"
            )

    if sum(1 for vlan in site.vlans if vlan.management) > 1:
        problems.append(f"{where}: more than one VLAN is marked as management")

    ports = sum(max(vlan.ports, 0) for vlan in site.vlans)
    available = network.hardware.switch_access_ports
    if ports > available:
        problems.append(
            f"{where}: {ports} access ports are assigned but the switch has only {available}"
        )


def _check_links(network: Network, problems: list[str]) -> None:
    names = {site.name for site in network.sites}
    seen: set[frozenset[str]] = set()

    for index, link in enumerate(network.links):
        where = f"links[{index}]"
        unknown = [end for end in (link.a, link.b) if end not in names]
        for end in unknown:
            problems.append(f"{where}: there is no site named {end!r}")
        if link.a == link.b:
            problems.append(f"{where}: a link needs two different sites")
        elif not unknown:
            pair = frozenset((link.a, link.b))
            if pair in seen:
                problems.append(f"{where}: {link.a} and {link.b} are already linked")
            seen.add(pair)

    if any(problem.startswith("links[") for problem in problems):
        return

    try:
        assign_link_interfaces(network)
    except InterfaceError as error:
        problems.append(f"links: {error}")

    # Walk the links from the first site. A site that is never reached is
    # cut off from the rest of the network.
    if len(network.sites) > 1:
        reached = {network.sites[0].name}
        frontier = [network.sites[0].name]
        while frontier:
            current = frontier.pop()
            for link in network.links:
                if current in (link.a, link.b):
                    other = link.b if link.a == current else link.a
                    if other not in reached:
                        reached.add(other)
                        frontier.append(other)
        for index, site in enumerate(network.sites):
            if site.name not in reached:
                problems.append(
                    f"sites[{index}]: {site.name} is not connected to "
                    f"{network.sites[0].name} by any chain of links"
                )


def find_problems(network: Network) -> list[str]:
    problems: list[str] = []

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", network.name):
        problems.append("name: must be 1-40 letters, digits, hyphens or underscores")
    if not network.sites:
        problems.append("sites: at least one site is required")
    if len(network.sites) > 200:
        # Router ids are derived from the position of the site (1.1.1.1, ...).
        problems.append("sites: more than 200 sites are not supported")
    if network.native_vlan is not None:
        _check_vlan_id(network.native_vlan, "native_vlan", problems)

    seen: set[str] = set()
    for index, site in enumerate(network.sites):
        if site.name in seen:
            problems.append(f"sites[{index}].name: {site.name!r} is used twice")
        seen.add(site.name)
        _check_site(network, site, f"sites[{index}]", problems)

    edges = [index for index, site in enumerate(network.sites) if site.internet]
    for index in edges[1:]:
        problems.append(
            f"sites[{index}].internet: only one site can have the internet uplink "
            f"(already defined in sites[{edges[0]}])"
        )
    for index in edges[:1]:
        site = network.sites[index]
        where = f"sites[{index}].internet"
        uplink = site.internet
        if uplink.interface == network.hardware.router_lan:
            problems.append(f"{where}.interface: {uplink.interface} is the LAN interface")
        if uplink.gateway not in uplink.address.network:
            problems.append(f"{where}.gateway: {uplink.gateway} is not in {uplink.address.network}")
        elif uplink.gateway == uplink.address.ip:
            problems.append(f"{where}.gateway: is the same as the router's own address")
        if uplink.address.network.overlaps(network.block):
            problems.append(
                f"{where}.address: {uplink.address.network} overlaps the internal "
                f"block {network.block}"
            )

    _check_links(network, problems)
    return problems


def validate(network: Network) -> Network:
    """Returns the network unchanged, or raises ConfigError with every problem."""
    problems = find_problems(network)
    if problems:
        raise ConfigError(problems)
    return network
