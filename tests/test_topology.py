import json

from subnetplan.cli import main
from subnetplan.loader import parse_network
from subnetplan.plan import build_plan
from subnetplan.topology import to_topology


def test_nodes(lab):
    topology = to_topology(build_plan(lab))
    assert topology["name"] == "lab"
    assert [(node["id"], node["kind"]) for node in topology["nodes"]] == [
        ("MAIN-R1", "router"),
        ("MAIN-SW1", "switch"),
        ("REMOTE-R1", "router"),
        ("REMOTE-SW1", "switch"),
        ("internet", "cloud"),
    ]
    switch = topology["nodes"][1]
    assert switch["management_address"] == "10.0.0.146"
    assert switch["vlans"][0] == {"id": 10, "name": "users", "network": "10.0.0.0/25"}


def test_links(lab):
    links = to_topology(build_plan(lab))["links"]
    assert [(link["source"], link["target"], link["kind"]) for link in links] == [
        ("MAIN-R1", "MAIN-SW1", "trunk"),
        ("REMOTE-R1", "REMOTE-SW1", "trunk"),
        ("MAIN-R1", "REMOTE-R1", "wan"),
        ("MAIN-R1", "internet", "uplink"),
    ]
    wan = links[2]
    assert wan["network"] == "10.0.1.32/30"
    assert (wan["source_address"], wan["target_address"]) == ("10.0.1.33", "10.0.1.34")


def test_every_link_refers_to_existing_nodes(lab):
    topology = to_topology(build_plan(lab))
    ids = {node["id"] for node in topology["nodes"]}
    assert len(ids) == len(topology["nodes"])
    for link in topology["links"]:
        assert link["source"] in ids
        assert link["target"] in ids


def test_no_cloud_without_an_internet_uplink(raw):
    del raw["sites"][0]["internet"]
    topology = to_topology(build_plan(parse_network(raw)))
    assert all(node["kind"] != "cloud" for node in topology["nodes"])
    assert all(link["kind"] != "uplink" for link in topology["links"])


def test_build_writes_the_topology(tmp_path, capsys, examples):
    assert main(["build", str(examples / "acme.toml"), "--out", str(tmp_path)]) == 0
    topology = json.loads((tmp_path / "topology.json").read_text())
    assert len(topology["nodes"]) == 7
    assert len(topology["links"]) == 7
