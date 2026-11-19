from subnetplan.cli import main
from subnetplan.loader import load, parse_network
from subnetplan.plan import build_plan
from subnetplan.validate import validate
from subnetplan.verify import render_checklist


def test_checklist_covers_every_device(lab):
    text = render_checklist(build_plan(lab))
    for device in ("MAIN-R1", "MAIN-SW1", "REMOTE-R1", "REMOTE-SW1"):
        assert f"### {device}" in text


def test_manual_steps_come_first(lab):
    text = render_checklist(build_plan(lab))
    assert text.index("CHANGE-ME") < text.index("## Per device")
    assert "crypto key generate rsa general-keys modulus 2048" in text
    # No serial links in this network, so no clock rate step.
    assert "clock rate" not in text


def test_serial_links_get_a_clock_rate_step(examples):
    text = render_checklist(build_plan(validate(load(examples / "acme.toml"))))
    assert "3. Serial links (HQ-R1 - SOUTH-R1): set `clock rate 128000`" in text


def test_expected_ospf_neighbours(lab):
    lines = render_checklist(build_plan(lab)).splitlines()
    assert "  - 1 neighbour(s) in state `FULL`: REMOTE-R1 (2.2.2.2)." in lines
    assert "  - 1 neighbour(s) in state `FULL`: MAIN-R1 (1.1.1.1)." in lines
    # Only the branch learns the default route through OSPF.
    assert sum("`O*E2`" in line for line in lines) == 1


def test_switch_port_table(lab):
    lines = render_checklist(build_plan(lab)).splitlines()
    assert "| Fa0/1-10 | 10 | users |" in lines
    assert "| Fa0/11-12 | 20 | servers |" in lines
    assert "| Fa0/13 | 99 | management |" in lines
    assert "| Fa0/1-24 | 10 | users |" in lines


def test_end_to_end_tests_walk_outwards(lab):
    text = render_checklist(build_plan(lab))
    steps = [line for line in text.splitlines() if line[:1].isdigit() and "`ping" in line]
    assert steps == [
        "1. `ping 10.0.0.1` reaches its own gateway.",
        "2. `ping 10.0.0.129` reaches VLAN 20 (routing between VLANs).",
        "3. `ping 10.0.0.145` reaches VLAN 99 (routing between VLANs).",
        "4. `ping 10.0.1.1` reaches site remote (OSPF across the WAN).",
        "5. `ping 203.0.113.1` reaches the provider (default route and NAT).",
    ]
    # One link between two sites: there is no redundancy to test.
    assert "Shut down one WAN interface" not in text


def test_redundant_wan_gets_a_failover_test(examples):
    text = render_checklist(build_plan(validate(load(examples / "acme.toml"))))
    assert "Shut down one WAN" in text


def test_single_site_without_internet(raw):
    raw["sites"] = [raw["sites"][1]]
    raw["links"] = []
    text = render_checklist(build_plan(parse_network(raw)))
    assert "show ip ospf neighbor" not in text
    assert "show ip nat translations" not in text
    assert "1. `ping 10.0.0.1` reaches its own gateway." in text


def test_build_writes_the_checklist(tmp_path, capsys, examples):
    assert main(["build", str(examples / "acme.toml"), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "VERIFY.md").read_text().startswith("# Verification checklist: acme\n")
