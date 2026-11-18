import pytest

from subnetplan.loader import ConfigError, load, parse_network
from subnetplan.validate import find_problems, validate


def check(raw):
    return find_problems(parse_network(raw))


def test_base_description_and_example_are_valid(lab, examples):
    assert find_problems(lab) == []
    assert validate(lab) is lab
    assert find_problems(load(examples / "acme.toml")) == []


def test_validate_raises_with_every_problem(raw):
    raw["sites"][0]["vlans"][0]["hosts"] = 0
    raw["sites"][1]["name"] = "Remote Office"
    with pytest.raises(ConfigError) as caught:
        validate(parse_network(raw))
    assert len(caught.value.problems) >= 2


@pytest.mark.parametrize(
    ("vlan_id", "problem"),
    [
        (0, "sites[0].vlans[0].id: VLAN id 0 is outside 1-4094"),
        (4095, "sites[0].vlans[0].id: VLAN id 4095 is outside 1-4094"),
        (1, "sites[0].vlans[0].id: VLAN 1 is reserved on Cisco switches"),
        (1002, "sites[0].vlans[0].id: VLAN 1002 is reserved on Cisco switches"),
        (999, "sites[0].vlans[0].id: VLAN 999 is the native VLAN and cannot carry hosts"),
        # The second VLAN with the same id is the one that gets reported.
        (20, "sites[0].vlans[1].id: VLAN 20 is used twice in site main"),
    ],
)
def test_vlan_ids(raw, vlan_id, problem):
    raw["sites"][0]["vlans"][0]["id"] = vlan_id
    assert check(raw) == [problem]


def test_the_same_vlan_id_may_be_used_at_different_sites(lab):
    assert lab.site("main").vlans[0].id == lab.site("remote").vlans[0].id
    assert find_problems(lab) == []


def test_vlan_details(raw):
    vlans = raw["sites"][0]["vlans"]
    vlans[0]["name"] = "office users"
    vlans[0]["hosts"] = 0
    vlans[0]["port_security"] = 0
    vlans[1]["name"] = "Management"
    vlans[1]["ports"] = -1
    vlans[2]["dhcp"] = True
    assert check(raw) == [
        "sites[0].vlans[0].name: 'office users' must be 1-32 letters, digits, hyphens "
        "or underscores",
        "sites[0].vlans[0].hosts: must be at least 1",
        "sites[0].vlans[0].port_security: must be between 1 and 132",
        "sites[0].vlans[1].ports: cannot be negative",
        "sites[0].vlans[2].name: 'management' is used twice in site main",
        "sites[0].vlans[2]: a management VLAN holds statically addressed devices, set dhcp = false",
    ]


def test_only_one_management_vlan_per_site(raw):
    raw["sites"][0]["vlans"][1]["management"] = True
    assert check(raw) == ["sites[0]: more than one VLAN is marked as management"]


def test_access_ports_must_fit_on_the_switch(raw):
    raw["sites"][0]["vlans"][0]["ports"] = 22
    assert check(raw) == ["sites[0]: 25 access ports are assigned but the switch has only 24"]


def test_site_names(raw):
    raw["sites"][1]["name"] = "main"
    assert "sites[1].name: 'main' is used twice" in check(raw)

    raw["sites"][1]["name"] = "2nd-floor"
    assert any("must start with a letter" in problem for problem in check(raw))


def test_a_site_needs_vlans(raw):
    raw["sites"][1]["vlans"] = []
    assert check(raw) == ["sites[1]: a site needs at least one VLAN"]


def test_links_must_refer_to_two_different_existing_sites(raw):
    raw["links"] = [
        {"sites": ["main", "nowhere"]},
        {"sites": ["main", "main"]},
        {"sites": ["main", "remote"]},
        {"sites": ["remote", "main"]},
    ]
    assert check(raw) == [
        "links[0]: there is no site named 'nowhere'",
        "links[1]: a link needs two different sites",
        "links[3]: remote and main are already linked",
    ]


def test_every_site_must_be_reachable(raw):
    raw["sites"].append({"name": "island", "vlans": [{"id": 10, "name": "users", "hosts": 5}]})
    assert check(raw) == ["sites[2]: island is not connected to main by any chain of links"]

    raw["links"].append({"sites": ["remote", "island"]})
    assert check(raw) == []


def test_internet_uplink(raw):
    raw["sites"][1]["internet"] = dict(raw["sites"][0]["internet"])
    assert check(raw) == [
        "sites[1].internet: only one site can have the internet uplink "
        "(already defined in sites[0])"
    ]

    del raw["sites"][1]["internet"]
    raw["sites"][0]["internet"] = {
        "interface": "GigabitEthernet0/0",
        "address": "10.0.1.2/30",
        "gateway": "10.0.9.1",
    }
    assert check(raw) == [
        "sites[0].internet.interface: GigabitEthernet0/0 is the LAN interface",
        "sites[0].internet.gateway: 10.0.9.1 is not in 10.0.1.0/30",
        "sites[0].internet.address: 10.0.1.0/30 overlaps the internal block 10.0.0.0/22",
    ]

    raw["sites"][0]["internet"] = {
        "interface": "GigabitEthernet0/2",
        "address": "203.0.113.2/30",
        "gateway": "203.0.113.2",
    }
    assert check(raw) == ["sites[0].internet.gateway: is the same as the router's own address"]


def test_native_vlan_must_be_a_usable_id(raw):
    raw["native_vlan"] = 1
    assert check(raw) == ["native_vlan: VLAN 1 is reserved on Cisco switches"]
