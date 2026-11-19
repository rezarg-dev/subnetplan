"""Turns a network description into an addressing plan."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from subnetplan.calc import usable_hosts
from subnetplan.interfaces import assign_link_interfaces
from subnetplan.model import Link, Network, Site, Vlan
from subnetplan.vlsm import Request, allocate, free_blocks, place, smallest_block_prefix

_WAN = "wan"
_LINK_PREFIX = 30


@dataclass(frozen=True)
class VlanPlan:
    vlan: Vlan
    network: IPv4Network
    gateway: IPv4Address
    # Management address of the site's switch, in the management VLAN only.
    switch_address: IPv4Address | None
    # First and last address handed out by DHCP, or None without DHCP.
    dhcp_range: tuple[IPv4Address, IPv4Address] | None

    @property
    def usable(self) -> int:
        return usable_hosts(self.network.prefixlen)


@dataclass(frozen=True)
class SitePlan:
    site: Site
    # One block per site, so the whole site can be described by one route.
    summary: IPv4Network
    router_id: IPv4Address
    vlans: tuple[VlanPlan, ...]

    @property
    def management(self) -> VlanPlan | None:
        for vlan in self.vlans:
            if vlan.vlan.management:
                return vlan
        return None


@dataclass(frozen=True)
class LinkEnd:
    site: Site
    interface: str
    address: IPv4Address


@dataclass(frozen=True)
class LinkPlan:
    link: Link
    network: IPv4Network
    a: LinkEnd
    b: LinkEnd

    def end(self, site_name: str) -> LinkEnd:
        return self.a if self.a.site.name == site_name else self.b

    def other(self, site_name: str) -> LinkEnd:
        return self.b if self.a.site.name == site_name else self.a


@dataclass(frozen=True)
class Plan:
    network: Network
    sites: tuple[SitePlan, ...]
    links: tuple[LinkPlan, ...]
    # Block the link subnets are taken from, or None without links.
    wan_block: IPv4Network | None
    free: tuple[IPv4Network, ...]

    def site(self, name: str) -> SitePlan:
        for site in self.sites:
            if site.site.name == name:
                return site
        raise KeyError(name)

    def links_of(self, site_name: str) -> list[LinkPlan]:
        return [link for link in self.links if site_name in (link.link.a, link.link.b)]

    @property
    def hosts_requested(self) -> int:
        return sum(vlan.vlan.hosts for site in self.sites for vlan in site.vlans)

    @property
    def addresses_allocated(self) -> int:
        blocks = [site.summary for site in self.sites]
        if self.wan_block:
            blocks.append(self.wan_block)
        return sum(block.num_addresses for block in blocks)


def _site_requests(site: Site) -> list[Request]:
    return [Request(str(vlan.id), vlan.addresses_needed) for vlan in site.vlans]


def _plan_vlan(vlan: Vlan, network: IPv4Network) -> VlanPlan:
    # The gateway is always the first usable address. The switch, if it lives
    # in this VLAN, takes the second. DHCP hands out whatever comes after.
    gateway = network[1]
    switch_address = network[2] if vlan.management else None
    dhcp_range = None
    if vlan.dhcp:
        first_dynamic = network[3] if vlan.management else network[2]
        dhcp_range = (first_dynamic, network[-2])
    return VlanPlan(vlan, network, gateway, switch_address, dhcp_range)


def _plan_site(site: Site, block: IPv4Network, index: int) -> SitePlan:
    networks = {a.name: a.network for a in allocate(block, _site_requests(site))}
    vlans = [_plan_vlan(vlan, networks[str(vlan.id)]) for vlan in site.vlans]
    vlans.sort(key=lambda plan: plan.vlan.id)
    # 1.1.1.1, 2.2.2.2, ...: easy to recognise in "show ip ospf neighbor".
    octet = index + 1
    router_id = IPv4Address(f"{octet}.{octet}.{octet}.{octet}")
    return SitePlan(site, block, router_id, tuple(vlans))


def _plan_links(network: Network, wan_block: IPv4Network) -> list[LinkPlan]:
    interfaces = assign_link_interfaces(network)
    subnets = wan_block.subnets(new_prefix=_LINK_PREFIX)

    plans = []
    for link, (interface_a, interface_b), subnet in zip(
        network.links, interfaces, subnets, strict=False
    ):
        end_a = LinkEnd(network.site(link.a), interface_a, subnet[1])
        end_b = LinkEnd(network.site(link.b), interface_b, subnet[2])
        plans.append(LinkPlan(link, subnet, end_a, end_b))
    return plans


def build_plan(network: Network) -> Plan:
    """Assigns a block to every site and a subnet to every VLAN and link.

    Addresses are allocated in two levels. First each site gets one
    contiguous block that is just large enough for its VLANs, and the WAN
    links share one more block. Then the VLANs are placed inside their
    site's block. This costs a few addresses compared to one flat VLSM run,
    but every site can be summarised as a single prefix.

    Expects a network that passed `validate`. Raises AllocationError if the
    block is too small.
    """
    items = []
    for site in network.sites:
        prefixes = [request.prefix for request in _site_requests(site)]
        items.append((site.name, smallest_block_prefix(prefixes)))
    if network.links:
        items.append((_WAN, smallest_block_prefix([_LINK_PREFIX] * len(network.links))))

    blocks = {a.name: a.network for a in place(network.block, items)}

    sites = [_plan_site(site, blocks[site.name], index) for index, site in enumerate(network.sites)]
    wan_block = blocks.get(_WAN)
    links = _plan_links(network, wan_block) if wan_block else []
    free = free_blocks(network.block, list(blocks.values()))

    return Plan(network, tuple(sites), tuple(links), wan_block, tuple(free))
