import csv
import io
import json

from subnetplan.cli import main
from subnetplan.export import to_csv, to_dict, to_json, to_markdown
from subnetplan.plan import build_plan


def test_dict_contains_the_whole_plan(lab):
    data = to_dict(build_plan(lab))

    assert data["name"] == "lab"
    assert data["block"] == "10.0.0.0/22"
    assert data["wan_block"] == "10.0.1.32/30"
    assert data["hosts_requested"] == 132

    main_site = data["sites"][0]
    assert main_site["summary"] == "10.0.0.0/24"
    assert main_site["router"] == {"hostname": "MAIN-R1", "router_id": "1.1.1.1"}
    assert main_site["switch"] == {"hostname": "MAIN-SW1", "management_address": "10.0.0.146"}
    assert main_site["vlans"][0] == {
        "id": 10,
        "name": "users",
        "hosts": 100,
        "network": "10.0.0.0/25",
        "netmask": "255.255.255.128",
        "gateway": "10.0.0.1",
        "usable": 126,
        "dhcp_range": ["10.0.0.2", "10.0.0.126"],
    }
    assert main_site["vlans"][1]["dhcp_range"] is None
    assert data["sites"][1]["switch"]["management_address"] is None

    assert data["links"] == [
        {
            "network": "10.0.1.32/30",
            "ends": [
                {
                    "site": "main",
                    "router": "MAIN-R1",
                    "interface": "GigabitEthernet0/1",
                    "address": "10.0.1.33",
                },
                {
                    "site": "remote",
                    "router": "REMOTE-R1",
                    "interface": "GigabitEthernet0/1",
                    "address": "10.0.1.34",
                },
            ],
        }
    ]


def test_json_round_trips(lab):
    plan = build_plan(lab)
    assert json.loads(to_json(plan)) == to_dict(plan)
    assert to_json(plan).endswith("}\n")


def test_csv_has_one_row_per_subnet(lab):
    rows = list(csv.DictReader(io.StringIO(to_csv(build_plan(lab)))))

    assert len(rows) == 5
    assert rows[0] == {
        "site": "main",
        "kind": "vlan",
        "vlan": "10",
        "name": "users",
        "network": "10.0.0.0/25",
        "netmask": "255.255.255.128",
        "gateway": "10.0.0.1",
        "dhcp_first": "10.0.0.2",
        "dhcp_last": "10.0.0.126",
    }
    assert rows[1]["dhcp_first"] == ""
    assert rows[4]["kind"] == "link"
    assert rows[4]["name"] == "main-remote"
    assert rows[4]["network"] == "10.0.1.32/30"


def test_markdown(lab):
    text = to_markdown(build_plan(lab))
    lines = text.splitlines()

    assert lines[0] == "# Addressing plan: lab"
    assert "## Site main" in lines
    assert "| VLAN | Name | Hosts | Subnet | Mask | Gateway | DHCP |" in lines
    assert (
        "| 10 | users | 100 | `10.0.0.0/25` | 255.255.255.128 | 10.0.0.1 "
        "| 10.0.0.2 to 10.0.0.126 |" in lines
    )
    assert (
        "| 20 | servers | 10 | `10.0.0.128/28` | 255.255.255.240 | 10.0.0.129 | static |" in lines
    )
    assert "## WAN links" in lines
    assert "## Free space" in lines
    assert text.endswith("\n")


def test_markdown_without_links_has_no_wan_section(raw):
    from subnetplan.loader import parse_network

    raw["sites"] = raw["sites"][:1]
    raw["links"] = []
    assert "## WAN links" not in to_markdown(build_plan(parse_network(raw)))


def test_format_option(capsys, examples):
    path = str(examples / "acme.toml")

    assert main(["plan", path, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "acme"

    assert main(["plan", path, "--format", "csv"]) == 0
    assert capsys.readouterr().out.startswith("site,kind,vlan,name,network,")

    assert main(["plan", path, "--format", "markdown"]) == 0
    assert capsys.readouterr().out.startswith("# Addressing plan: acme\n")
