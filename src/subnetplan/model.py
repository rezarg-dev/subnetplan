"""The network as the user describes it, before any address is assigned."""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Interface, IPv4Network


@dataclass(frozen=True)
class Vlan:
    id: int
    name: str
    # End devices that need an address. The gateway is added on top.
    hosts: int
    # Whether the site router hands out addresses for this VLAN.
    dhcp: bool = True
    # The switch gets its management address in this VLAN.
    management: bool = False
    # Number of access ports on the switch assigned to this VLAN.
    ports: int = 0
    # Maximum number of MAC addresses per port, or None for no port security.
    port_security: int | None = None

    @property
    def addresses_needed(self) -> int:
        return self.hosts + 1 + (1 if self.management else 0)


@dataclass(frozen=True)
class Internet:
    """Uplink to a provider. The site that has one does NAT for all sites."""

    interface: str
    address: IPv4Interface
    gateway: IPv4Address


@dataclass(frozen=True)
class Site:
    name: str
    vlans: tuple[Vlan, ...]
    internet: Internet | None = None

    @property
    def router(self) -> str:
        return f"{self.name.upper()}-R1"

    @property
    def switch(self) -> str:
        return f"{self.name.upper()}-SW1"


@dataclass(frozen=True)
class Link:
    """A point-to-point connection between the routers of two sites."""

    a: str
    b: str


@dataclass(frozen=True)
class Hardware:
    """Interface names of the devices the configuration is generated for.

    The defaults match a Cisco 2911 router and a 2960 switch, the pair most
    Packet Tracer labs use.
    """

    router_lan: str = "GigabitEthernet0/0"
    router_wan: tuple[str, ...] = (
        "GigabitEthernet0/1",
        "GigabitEthernet0/2",
        "Serial0/0/0",
        "Serial0/0/1",
    )
    switch_uplink: str = "GigabitEthernet0/1"
    switch_access_prefix: str = "FastEthernet0/"
    switch_access_ports: int = 24
    # Ports that exist but are not used by the design. They are shut down.
    switch_spare: tuple[str, ...] = ("GigabitEthernet0/2",)


@dataclass(frozen=True)
class Network:
    name: str
    block: IPv4Network
    sites: tuple[Site, ...]
    links: tuple[Link, ...] = ()
    domain: str = "example.internal"
    dns_servers: tuple[IPv4Address, ...] = ()
    # Untagged VLAN on trunks. Using an otherwise empty VLAN instead of the
    # default VLAN 1 prevents VLAN hopping through double tagging.
    native_vlan: int | None = None
    hardware: Hardware = field(default_factory=Hardware)

    def site(self, name: str) -> Site:
        for site in self.sites:
            if site.name == name:
                return site
        raise KeyError(name)

    @property
    def edge(self) -> Site | None:
        """The site with the internet uplink, if there is one."""
        for site in self.sites:
            if site.internet is not None:
                return site
        return None
