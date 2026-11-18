from subnetplan.ios import router
from subnetplan.loader import parse_network
from subnetplan.plan import build_plan


def test_one_subinterface_per_vlan(lab):
    site = build_plan(lab).site("main")
    assert router.lan_interfaces(site, lab) == [
        "interface GigabitEthernet0/0",
        " description Trunk to MAIN-SW1",
        " no ip address",
        " no shutdown",
        "!",
        "interface GigabitEthernet0/0.10",
        " description users",
        " encapsulation dot1Q 10",
        " ip address 10.0.0.1 255.255.255.128",
        "!",
        "interface GigabitEthernet0/0.20",
        " description servers",
        " encapsulation dot1Q 20",
        " ip address 10.0.0.129 255.255.255.240",
        "!",
        "interface GigabitEthernet0/0.99",
        " description management",
        " encapsulation dot1Q 99",
        " ip address 10.0.0.145 255.255.255.248",
        "!",
        "interface GigabitEthernet0/0.999",
        " description native VLAN, no hosts",
        " encapsulation dot1Q 999 native",
    ]


def test_encapsulation_comes_before_the_address(lab):
    # IOS refuses an IP address on a subinterface that has no encapsulation yet.
    lines = router.lan_interfaces(build_plan(lab).site("main"), lab)
    for index, line in enumerate(lines):
        if line.startswith(" ip address"):
            assert lines[index - 1].startswith(" encapsulation dot1Q")


def test_nat_inside_on_every_addressed_subinterface(lab):
    lines = router.lan_interfaces(build_plan(lab).site("main"), lab, nat_inside=True)
    assert lines.count(" ip nat inside") == 3
    for index, line in enumerate(lines):
        if line == " ip nat inside":
            assert lines[index - 1].startswith(" ip address")


def test_no_native_subinterface_without_a_native_vlan(raw):
    del raw["native_vlan"]
    network = parse_network(raw)
    lines = router.lan_interfaces(build_plan(network).site("main"), network)
    assert not any("native" in line for line in lines)


def test_dhcp_pools_only_for_vlans_that_want_them(lab):
    site = build_plan(lab).site("main")
    assert router.dhcp(site, lab) == [
        "ip dhcp excluded-address 10.0.0.1",
        "!",
        "ip dhcp pool USERS",
        " network 10.0.0.0 255.255.255.128",
        " default-router 10.0.0.1",
        " dns-server 9.9.9.9",
        " domain-name lab.example",
    ]


def test_dhcp_without_dns_servers(raw):
    del raw["dns_servers"]
    network = parse_network(raw)
    lines = router.dhcp(build_plan(network).site("remote"), network)
    assert not any("dns-server" in line for line in lines)
    assert " default-router 10.0.1.1" in lines


def test_no_dhcp_section_when_no_vlan_uses_it(raw):
    for vlan in raw["sites"][0]["vlans"]:
        vlan["dhcp"] = False
    network = parse_network(raw)
    assert router.dhcp(build_plan(network).site("main"), network) == []
