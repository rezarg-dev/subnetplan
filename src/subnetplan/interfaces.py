"""Decides which router interfaces the WAN links use."""

from __future__ import annotations

import re

from subnetplan.model import Network


class InterfaceError(ValueError):
    """A link cannot be given an interface on both of its routers."""


def media(interface: str) -> str:
    """The interface type without its number: GigabitEthernet0/1 -> GigabitEthernet."""
    return re.match(r"[A-Za-z-]*", interface).group()


def assign_link_interfaces(network: Network) -> list[tuple[str, str]]:
    """Returns (interface on site a, interface on site b) for every link.

    Both ends of a cable need the same kind of port: a serial interface
    cannot be plugged into an Ethernet one. For each link, in the order
    they are listed, this picks the first interface type that still has a
    free port on both routers.
    """
    free = {}
    for site in network.sites:
        uplink = site.internet.interface if site.internet else None
        free[site.name] = [name for name in network.hardware.router_wan if name != uplink]

    assigned = []
    for link in network.links:
        match = None
        for candidate in free[link.a]:
            partner = next((n for n in free[link.b] if media(n) == media(candidate)), None)
            if partner is not None:
                match = (candidate, partner)
                break
        if match is None:
            raise InterfaceError(
                f"no interface left for the link {link.a} - {link.b}: the two routers have "
                "no free port of the same type"
            )
        free[link.a].remove(match[0])
        free[link.b].remove(match[1])
        assigned.append(match)
    return assigned
