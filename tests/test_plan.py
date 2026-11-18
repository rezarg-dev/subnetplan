from ipaddress import IPv4Address, IPv4Network

import pytest

from subnetplan.loader import load, parse_network
from subnetplan.plan import build_plan
from subnetplan.validate import validate
from subnetplan.vlsm import AllocationError


def test_lab_plan(lab):
    plan = build_plan(lab)

    main = plan.site("main")
    assert main.summary == IPv4Network("10.0.0.0/24")
    assert main.router_id == IPv4Address("1.1.1.1")
    assert {v.vlan.name: str(v.network) for v in main.vlans} == {
        "users": "10.0.0.0/25",
        "servers": "10.0.0.128/28",
        "management": "10.0.0.144/29",
    }

    remote = plan.site("remote")
    assert remote.summary == IPv4Network("10.0.1.0/27")
    assert remote.router_id == IPv4Address("2.2.2.2")

    assert plan.wan_block == IPv4Network("10.0.1.32/30")
    assert [str(block) for block in plan.free] == [
        "10.0.1.36/30",
        "10.0.1.40/29",
        "10.0.1.48/28",
        "10.0.1.64/26",
        "10.0.1.128/25",
        "10.0.2.0/23",
    ]
    assert plan.hosts_requested == 132
    assert plan.addresses_allocated == 256 + 32 + 4


def test_gateway_switch_and_dhcp_addresses(lab):
    users, servers, management = build_plan(lab).site("main").vlans

    assert users.gateway == IPv4Address("10.0.0.1")
    assert users.switch_address is None
    assert users.dhcp_range == (IPv4Address("10.0.0.2"), IPv4Address("10.0.0.126"))

    assert servers.gateway == IPv4Address("10.0.0.129")
    assert servers.dhcp_range is None

    assert management.gateway == IPv4Address("10.0.0.145")
    assert management.switch_address == IPv4Address("10.0.0.146")
    assert management.dhcp_range is None


def test_vlans_are_listed_by_id_whatever_their_size(raw):
    raw["sites"][0]["vlans"].reverse()
    plan = build_plan(parse_network(raw))
    assert [v.vlan.id for v in plan.site("main").vlans] == [10, 20, 99]
    # Allocation is still largest first.
    assert str(plan.site("main").vlans[0].network) == "10.0.0.0/25"


def test_smallest_possible_vlans(raw):
    raw["sites"][1]["vlans"] = [
        {"id": 10, "name": "one", "hosts": 1},
        {"id": 99, "name": "management", "hosts": 1, "dhcp": False, "management": True},
    ]
    one, management = build_plan(parse_network(raw)).site("remote").vlans

    assert one.network.prefixlen == 30
    assert one.dhcp_range == (one.network[2], one.network[2])
    # Gateway, switch and one host need three addresses: a /30 is too small.
    assert management.network.prefixlen == 29
    assert management.switch_address == management.network[2]


def test_links_get_addresses_and_matching_interfaces(lab):
    plan = build_plan(lab)
    (link,) = plan.links

    assert link.network == IPv4Network("10.0.1.32/30")
    assert (link.a.site.name, link.a.address) == ("main", IPv4Address("10.0.1.33"))
    assert (link.b.site.name, link.b.address) == ("remote", IPv4Address("10.0.1.34"))
    # main uses Gi0/2 for the internet, so the link gets Gi0/1 on both ends.
    assert (link.a.interface, link.b.interface) == ("GigabitEthernet0/1", "GigabitEthernet0/1")

    assert link.end("remote") is link.b
    assert link.other("remote") is link.a
    assert plan.links_of("main") == [link]


def test_nothing_overlaps_in_the_example(examples):
    plan = build_plan(validate(load(examples / "acme.toml")))
    block = plan.network.block

    summaries = [site.summary for site in plan.sites] + [plan.wan_block]
    for index, left in enumerate(summaries):
        assert left.subnet_of(block)
        for right in summaries[index + 1 :]:
            assert not left.overlaps(right)

    for site in plan.sites:
        for vlan in site.vlans:
            assert vlan.network.subnet_of(site.summary)
            assert vlan.usable >= vlan.vlan.addresses_needed
    for link in plan.links:
        assert link.network.subnet_of(plan.wan_block)

    covered = sum(n.num_addresses for n in summaries) + sum(n.num_addresses for n in plan.free)
    assert covered == block.num_addresses


def test_single_site_without_links(raw):
    raw["sites"] = raw["sites"][:1]
    raw["links"] = []
    plan = build_plan(validate(parse_network(raw)))
    assert plan.links == ()
    assert plan.wan_block is None
    assert [str(block) for block in plan.free] == ["10.0.1.0/24", "10.0.2.0/23"]


def test_block_too_small(raw):
    raw["block"] = "10.0.0.0/25"
    with pytest.raises(AllocationError, match="larger than the whole block"):
        build_plan(parse_network(raw))

    raw["block"] = "10.0.0.0/24"
    with pytest.raises(AllocationError, match=r"292 addresses are needed.*at least a /23"):
        build_plan(parse_network(raw))
