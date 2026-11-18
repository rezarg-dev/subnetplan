from ipaddress import IPv4Address, IPv4Network

import pytest

from subnetplan.loader import ConfigError, load, parse_network


def problems(raw):
    with pytest.raises(ConfigError) as caught:
        parse_network(raw)
    return caught.value.problems


def test_base_description_parses(lab):
    assert lab.name == "lab"
    assert lab.block == IPv4Network("10.0.0.0/22")
    assert lab.dns_servers == (IPv4Address("9.9.9.9"),)
    assert [site.name for site in lab.sites] == ["main", "remote"]

    main = lab.site("main")
    assert main.router == "MAIN-R1"
    assert main.switch == "MAIN-SW1"
    assert main.internet.gateway == IPv4Address("203.0.113.1")
    assert [vlan.id for vlan in main.vlans] == [10, 20, 99]
    assert main.vlans[0].port_security == 2
    assert main.vlans[1].dhcp is False
    assert lab.edge is main


def test_defaults(raw):
    del raw["domain"], raw["dns_servers"], raw["native_vlan"], raw["links"]
    raw["sites"] = [{"name": "only", "vlans": [{"id": 10, "name": "users", "hosts": 5}]}]
    network = parse_network(raw)

    assert network.domain == "example.internal"
    assert network.dns_servers == ()
    assert network.native_vlan is None
    assert network.links == ()
    assert network.edge is None
    vlan = network.sites[0].vlans[0]
    assert (vlan.dhcp, vlan.management, vlan.ports, vlan.port_security) == (True, False, 0, None)
    assert network.hardware.router_lan == "GigabitEthernet0/0"


def test_addresses_needed_includes_gateway_and_switch(lab):
    users, servers, management = lab.site("main").vlans
    assert users.addresses_needed == 101
    assert servers.addresses_needed == 11
    assert management.addresses_needed == 4


def test_missing_required_values_are_all_reported(raw):
    del raw["name"], raw["block"]
    del raw["sites"][0]["vlans"][0]["hosts"]
    assert problems(raw) == [
        "name: is required",
        "block: is required",
        "sites[0].vlans[0].hosts: is required",
    ]


def test_wrong_types_are_reported_with_their_location(raw):
    raw["block"] = "10.0.0.0/33"
    raw["dns_servers"] = ["dns.example"]
    raw["sites"][0]["vlans"][0]["hosts"] = "100"
    raw["sites"][0]["vlans"][1]["dhcp"] = "no"
    raw["sites"][1]["vlans"][0]["ports"] = True
    raw["links"][0]["sites"] = ["main"]
    assert problems(raw) == [
        "block: '10.0.0.0/33' is not a network like 10.20.0.0/21",
        "dns_servers[0]: 'dns.example' is not an IPv4 address",
        "sites[0].vlans[0].hosts: must be an integer",
        "sites[0].vlans[1].dhcp: must be true or false",
        "sites[1].vlans[0].ports: must be an integer",
        "links[0].sites: must name exactly two sites",
    ]


def test_block_with_host_bits_set_is_rejected(raw):
    raw["block"] = "10.0.0.1/22"
    assert problems(raw) == ["block: '10.0.0.1/22' is not a network like 10.20.0.0/21"]


def test_unknown_keys_catch_typos(raw):
    raw["dns_server"] = ["9.9.9.9"]
    raw["sites"][0]["vlans"][0]["host"] = 5
    raw["sites"][0]["internet"]["gatway"] = "203.0.113.1"
    assert problems(raw) == [
        "dns_server: unknown key",
        "sites[0].vlans[0].host: unknown key",
        "sites[0].internet.gatway: unknown key",
    ]


def test_hardware_can_be_overridden(raw):
    raw["hardware"] = {
        "router_lan": "GigabitEthernet0/0/0",
        "router_wan": ["GigabitEthernet0/0/1", "Serial0/1/0"],
        "switch_access_ports": 48,
    }
    hardware = parse_network(raw).hardware
    assert hardware.router_lan == "GigabitEthernet0/0/0"
    assert hardware.router_wan == ("GigabitEthernet0/0/1", "Serial0/1/0")
    assert hardware.switch_access_ports == 48
    assert hardware.switch_uplink == "GigabitEthernet0/1"


def test_load_reads_the_example_file(examples):
    network = load(examples / "acme.toml")
    assert network.name == "acme"
    assert [site.name for site in network.sites] == ["hq", "north", "south"]
    assert len(network.links) == 3


def test_load_reports_missing_and_broken_files(tmp_path):
    with pytest.raises(ConfigError, match="No such file"):
        load(tmp_path / "missing.toml")

    broken = tmp_path / "broken.toml"
    broken.write_text('name = "x"\nblock = \n')
    with pytest.raises(ConfigError, match="not valid TOML"):
        load(broken)
