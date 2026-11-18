from subnetplan.ios import routing
from subnetplan.loader import load, parse_network
from subnetplan.plan import build_plan
from subnetplan.validate import validate


def test_wan_interface(lab):
    plan = build_plan(lab)
    assert routing.wan_interfaces(plan, plan.site("remote")) == [
        "interface GigabitEthernet0/1",
        " description Link to MAIN-R1",
        " ip address 10.0.1.34 255.255.255.252",
        " no shutdown",
    ]


def test_wan_interfaces_of_the_edge_router_are_nat_inside(lab):
    plan = build_plan(lab)
    lines = routing.wan_interfaces(plan, plan.site("main"), nat_inside=True)
    assert lines == [
        "interface GigabitEthernet0/1",
        " description Link to REMOTE-R1",
        " ip address 10.0.1.33 255.255.255.252",
        " ip nat inside",
        " no shutdown",
    ]


def test_ospf_on_the_edge_router(lab):
    plan = build_plan(lab)
    assert routing.ospf(plan, plan.site("main")) == [
        "router ospf 1",
        " router-id 1.1.1.1",
        " passive-interface default",
        " no passive-interface GigabitEthernet0/1",
        " network 10.0.0.0 0.0.0.127 area 0",
        " network 10.0.0.128 0.0.0.15 area 0",
        " network 10.0.0.144 0.0.0.7 area 0",
        " network 10.0.1.32 0.0.0.3 area 0",
        " default-information originate",
    ]


def test_ospf_on_a_branch_router(lab):
    plan = build_plan(lab)
    lines = routing.ospf(plan, plan.site("remote"))
    assert " router-id 2.2.2.2" in lines
    assert " network 10.0.1.0 0.0.0.31 area 0" in lines
    assert " default-information originate" not in lines


def test_ospf_covers_every_connected_subnet_and_only_those(examples):
    plan = build_plan(validate(load(examples / "acme.toml")))
    for site in plan.sites:
        statements = [
            line.split()[1:3] for line in routing.ospf(plan, site) if line.startswith(" network")
        ]
        expected = sorted(
            [vlan.network for vlan in site.vlans]
            + [link.network for link in plan.links_of(site.site.name)]
        )
        assert statements == [[str(n.network_address), str(n.hostmask)] for n in expected]

        active = [
            line.split()[-1]
            for line in routing.ospf(plan, site)
            if line.startswith(" no passive-interface")
        ]
        assert active == [
            link.end(site.site.name).interface for link in plan.links_of(site.site.name)
        ]


def test_no_ospf_for_a_single_site(raw):
    raw["sites"] = raw["sites"][:1]
    raw["links"] = []
    plan = build_plan(parse_network(raw))
    assert routing.ospf(plan, plan.site("main")) == []
    assert routing.wan_interfaces(plan, plan.site("main")) == []
