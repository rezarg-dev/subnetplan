import pytest

from subnetplan.interfaces import InterfaceError, assign_link_interfaces, media
from subnetplan.loader import load, parse_network
from subnetplan.plan import build_plan
from subnetplan.validate import find_problems, validate


def test_media():
    assert media("GigabitEthernet0/1") == "GigabitEthernet"
    assert media("Serial0/0/0") == "Serial"
    assert media("TenGigabitEthernet1/1/1") == "TenGigabitEthernet"


def test_first_common_interface_type_is_used(lab):
    # main uses Gi0/2 for the internet, so Gi0/1 is its first free port.
    assert assign_link_interfaces(lab) == [("GigabitEthernet0/1", "GigabitEthernet0/1")]


def test_both_ends_of_every_link_have_the_same_type(examples):
    plan = build_plan(validate(load(examples / "acme.toml")))
    for link in plan.links:
        assert media(link.a.interface) == media(link.b.interface), (
            f"{link.a.site.router} {link.a.interface} is cabled to "
            f"{link.b.site.router} {link.b.interface}"
        )


def test_router_without_free_ethernet_falls_back_to_serial(examples):
    plan = build_plan(validate(load(examples / "acme.toml")))
    interfaces = {
        (link.link.a, link.link.b): (link.a.interface, link.b.interface) for link in plan.links
    }
    # hq has one Ethernet port left after the internet uplink. Its second
    # link is serial on both ends, although south still has Ethernet ports.
    assert interfaces == {
        ("hq", "north"): ("GigabitEthernet0/1", "GigabitEthernet0/1"),
        ("hq", "south"): ("Serial0/0/0", "Serial0/0/0"),
        ("north", "south"): ("GigabitEthernet0/2", "GigabitEthernet0/1"),
    }


def test_no_port_is_used_twice(examples):
    plan = build_plan(validate(load(examples / "acme.toml")))
    used = [(end.site.name, end.interface) for link in plan.links for end in (link.a, link.b)]
    assert len(used) == len(set(used))
    assert ("hq", "GigabitEthernet0/2") not in used  # the internet uplink


def test_link_without_a_common_free_type_is_a_validation_problem(raw):
    raw["hardware"] = {"router_wan": ["GigabitEthernet0/1", "GigabitEthernet0/2"]}
    for name in ("b", "c"):
        raw["sites"].append({"name": name, "vlans": [{"id": 10, "name": "users", "hosts": 5}]})
        raw["links"].append({"sites": ["main", name]})
    network = parse_network(raw)

    # main: Gi0/2 is the internet uplink, which leaves one port for three links.
    with pytest.raises(InterfaceError):
        assign_link_interfaces(network)
    assert find_problems(network) == [
        "links: no interface left for the link main - b: the two routers have no free port "
        "of the same type"
    ]
