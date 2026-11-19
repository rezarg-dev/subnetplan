import json

from subnetplan.cli import main
from subnetplan.ios.device import render_all, render_router, render_switch
from subnetplan.loader import parse_network
from subnetplan.plan import build_plan


def sections(config):
    """Top-level commands of a configuration, in order."""
    return [line for line in config.splitlines() if line and not line.startswith((" ", "!"))]


def test_router_sections_come_in_a_loadable_order(lab):
    plan = build_plan(lab)
    top = sections(render_router(plan, plan.site("main")))

    assert top[0] == "service password-encryption"
    assert top[-1] == "end"
    # Pools are defined before the interfaces that would start serving them.
    assert top.index("ip dhcp pool USERS") < top.index("interface GigabitEthernet0/0")
    # The interfaces exist before OSPF and NAT refer to them.
    assert top.index("interface GigabitEthernet0/1") < top.index("router ospf 1")
    assert top.index("interface GigabitEthernet0/2") < top.index(
        "ip nat inside source list 1 interface GigabitEthernet0/2 overload"
    )


def test_only_the_edge_router_does_nat(lab):
    plan = build_plan(lab)
    assert "ip nat" in render_router(plan, plan.site("main"))
    assert "ip nat" not in render_router(plan, plan.site("remote"))


def test_switch_config_has_no_routing(lab):
    plan = build_plan(lab)
    config = render_switch(plan, plan.site("main"))
    assert "router ospf" not in config
    assert "ip dhcp" not in config
    assert "line vty 0 15" in config
    assert config.endswith("!\nend\n")


def test_no_blank_lines_or_trailing_spaces(lab):
    for config in render_all(build_plan(lab)).values():
        for line in config.splitlines():
            assert line == line.rstrip()
            assert line != ""
        assert "!\n!\n" not in config


def test_one_file_per_device(lab):
    assert sorted(render_all(build_plan(lab))) == [
        "MAIN-R1.cfg",
        "MAIN-SW1.cfg",
        "REMOTE-R1.cfg",
        "REMOTE-SW1.cfg",
    ]


def test_single_site_router_has_no_ospf_but_still_nat(raw):
    raw["sites"] = raw["sites"][:1]
    raw["links"] = []
    plan = build_plan(parse_network(raw))
    config = render_router(plan, plan.site("main"))
    assert "router ospf" not in config
    assert "ip route 0.0.0.0 0.0.0.0 203.0.113.1" in config


def test_build_writes_all_files(capsys, tmp_path, examples):
    out = tmp_path / "out" / "acme"
    assert main(["build", str(examples / "acme.toml"), "--out", str(out)]) == 0

    written = {path.name for path in out.iterdir()}
    assert written >= {
        "HQ-R1.cfg",
        "HQ-SW1.cfg",
        "NORTH-R1.cfg",
        "NORTH-SW1.cfg",
        "SOUTH-R1.cfg",
        "SOUTH-SW1.cfg",
        "plan.json",
        "plan.md",
    }
    assert json.loads((out / "plan.json").read_text())["name"] == "acme"
    assert (out / "HQ-R1.cfg").read_text().startswith("!\n! HQ-R1\n")
    assert capsys.readouterr().out.count("wrote ") == len(written)


def test_build_writes_nothing_for_an_invalid_file(capsys, tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text('name = "bad"\n')
    out = tmp_path / "out"

    assert main(["build", str(path), "--out", str(out)]) == 2
    assert not out.exists()
    assert "block: is required" in capsys.readouterr().err
