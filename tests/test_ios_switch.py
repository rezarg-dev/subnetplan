from subnetplan.ios import switch
from subnetplan.loader import parse_network
from subnetplan.plan import build_plan


def test_port_range_command():
    assert switch.port_range("FastEthernet0/", 1, 12) == "interface range FastEthernet0/1 - 12"
    assert switch.port_range("FastEthernet0/", 7, 7) == "interface FastEthernet0/7"


def test_vlans_are_created_with_their_names(lab):
    assert switch.vlans(build_plan(lab).site("main"), lab) == [
        "vlan 10",
        " name users",
        "vlan 20",
        " name servers",
        "vlan 99",
        " name management",
        "vlan 999",
        " name native",
    ]


def test_uplink_is_a_trunk_limited_to_the_site_vlans(lab):
    assert switch.uplink(build_plan(lab).site("main"), lab) == [
        "interface GigabitEthernet0/1",
        " description Trunk to MAIN-R1",
        " switchport mode trunk",
        " switchport trunk native vlan 999",
        " switchport trunk allowed vlan 10,20,99",
        " switchport nonegotiate",
    ]


def test_uplink_without_native_vlan(raw):
    del raw["native_vlan"]
    network = parse_network(raw)
    lines = switch.uplink(build_plan(network).site("main"), network)
    assert not any("native" in line for line in lines)


def test_access_ports_are_handed_out_in_order(lab):
    assert switch.access_ports(build_plan(lab).site("main"), lab) == [
        "interface range FastEthernet0/1 - 10",
        " description users",
        " switchport mode access",
        " switchport access vlan 10",
        " switchport port-security",
        " switchport port-security maximum 2",
        " switchport port-security mac-address sticky",
        " switchport port-security violation restrict",
        " spanning-tree portfast",
        " spanning-tree bpduguard enable",
        "!",
        "interface range FastEthernet0/11 - 12",
        " description servers",
        " switchport mode access",
        " switchport access vlan 20",
        " spanning-tree portfast",
        " spanning-tree bpduguard enable",
        "!",
        "interface FastEthernet0/13",
        " description management",
        " switchport mode access",
        " switchport access vlan 99",
        " spanning-tree portfast",
        " spanning-tree bpduguard enable",
        "!",
        "interface range FastEthernet0/14 - 24",
        " description unused",
        " shutdown",
        "!",
        "interface GigabitEthernet0/2",
        " description unused",
        " shutdown",
    ]


def test_port_security_needs_access_mode_first(lab):
    # A port still in dynamic mode rejects "switchport port-security".
    lines = switch.access_ports(build_plan(lab).site("main"), lab)
    assert lines.index(" switchport mode access") < lines.index(" switchport port-security")


def test_every_port_is_configured_exactly_once(lab):
    lines = switch.access_ports(build_plan(lab).site("main"), lab)
    seen = []
    for line in lines:
        if line.startswith("interface range FastEthernet0/"):
            first, last = line.removeprefix("interface range FastEthernet0/").split(" - ")
            seen += range(int(first), int(last) + 1)
        elif line.startswith("interface FastEthernet0/"):
            seen.append(int(line.removeprefix("interface FastEthernet0/")))
    assert seen == list(range(1, 25))


def test_no_unused_range_when_all_ports_are_assigned(lab):
    lines = switch.access_ports(build_plan(lab).site("remote"), lab)
    assert lines[0] == "interface range FastEthernet0/1 - 24"
    assert lines.count(" shutdown") == 1  # only the spare uplink


def test_all_access_ports_unused(raw):
    for vlan in raw["sites"][1]["vlans"]:
        vlan["ports"] = 0
    network = parse_network(raw)
    lines = switch.access_ports(build_plan(network).site("remote"), network)
    assert lines[:3] == ["interface range FastEthernet0/1 - 24", " description unused", " shutdown"]


def test_management_interface(lab):
    assert switch.management(build_plan(lab).site("main")) == [
        "interface Vlan99",
        " description management",
        " ip address 10.0.0.146 255.255.255.248",
        " no shutdown",
        "!",
        "ip default-gateway 10.0.0.145",
    ]
    assert switch.management(build_plan(lab).site("remote")) == []
