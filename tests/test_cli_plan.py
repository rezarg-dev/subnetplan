from subnetplan.cli import main
from subnetplan.report import short_interface, table


def test_table_columns_are_as_wide_as_their_longest_cell():
    assert table(["VLAN", "Name"], [["10", "staff"], ["200", "it"]]) == [
        "  VLAN  Name",
        "  ----  -----",
        "  10    staff",
        "  200   it",
    ]


def test_short_interface_names():
    assert short_interface("GigabitEthernet0/1") == "Gi0/1"
    assert short_interface("FastEthernet0/24") == "Fa0/24"
    assert short_interface("Serial0/0/0") == "Se0/0/0"
    assert short_interface("Vlan99") == "Vlan99"


def test_plan_prints_sites_links_and_summary(capsys, examples):
    assert main(["plan", str(examples / "acme.toml")]) == 0
    out = capsys.readouterr().out

    assert out.startswith("Network acme   block 10.20.0.0/21\n")
    assert "Site hq   summary 10.20.0.0/23   router HQ-R1 (id 1.1.1.1)   switch HQ-SW1" in out
    assert (
        "  10    staff        180    10.20.0.0/24    255.255.255.0    10.20.0.1    "
        "10.20.0.2 - 10.20.0.254  254" in out
    )
    assert "  hq - south     10.20.2.196/30  HQ-R1 Se0/0/0 10.20.2.197" in out
    assert "  Addresses allocated  720 of 2048 (35%)" in out
    assert not any(line != line.rstrip() for line in out.splitlines())


def test_plan_reports_every_problem_in_the_file(capsys, tmp_path):
    path = tmp_path / "broken.toml"
    path.write_text(
        """
name = "broken"
block = "10.0.0.0/24"

[[sites]]
name = "Head Office"

[[sites.vlans]]
id = 1
name = "users"
hosts = 0
"""
    )
    assert main(["plan", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines()[0] == "subnetplan: 3 problem(s) in the network file:"
    assert "  - sites[0].vlans[0].id: VLAN 1 is reserved on Cisco switches" in captured.err
    assert "  - sites[0].vlans[0].hosts: must be at least 1" in captured.err


def test_plan_reports_a_block_that_is_too_small(capsys, tmp_path, examples):
    text = (examples / "acme.toml").read_text().replace("10.20.0.0/21", "10.20.0.0/23")
    path = tmp_path / "small.toml"
    path.write_text(text)

    assert main(["plan", str(path)]) == 2
    err = capsys.readouterr().err
    assert err == (
        "subnetplan: 10.20.0.0/23 is too small: 720 addresses are needed, "
        "which takes at least a /22\n"
    )
