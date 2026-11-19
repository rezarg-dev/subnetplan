from subnetplan.ios import edge
from subnetplan.plan import build_plan


def test_internet_uplink(lab):
    plan = build_plan(lab)
    assert edge.uplink(plan.site("main")) == [
        "interface GigabitEthernet0/2",
        " description Internet uplink",
        " ip address 203.0.113.2 255.255.255.252",
        " ip nat outside",
        " no shutdown",
    ]
    assert edge.uplink(plan.site("remote")) == []


def test_nat_translates_the_whole_block(lab):
    plan = build_plan(lab)
    assert edge.nat(plan, plan.site("main")) == [
        "ip route 0.0.0.0 0.0.0.0 203.0.113.1",
        "!",
        "access-list 1 permit 10.0.0.0 0.0.3.255",
        "ip nat inside source list 1 interface GigabitEthernet0/2 overload",
    ]
    assert edge.nat(plan, plan.site("remote")) == []
