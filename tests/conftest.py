import copy
from pathlib import Path

import pytest

from subnetplan.loader import parse_network

# A small but complete description that tests can copy and modify.
BASE = {
    "name": "lab",
    "block": "10.0.0.0/22",
    "domain": "lab.example",
    "dns_servers": ["9.9.9.9"],
    "native_vlan": 999,
    "sites": [
        {
            "name": "main",
            "internet": {
                "interface": "GigabitEthernet0/2",
                "address": "203.0.113.2/30",
                "gateway": "203.0.113.1",
            },
            "vlans": [
                {"id": 10, "name": "users", "hosts": 100, "ports": 10, "port_security": 2},
                {"id": 20, "name": "servers", "hosts": 10, "dhcp": False, "ports": 2},
                {
                    "id": 99,
                    "name": "management",
                    "hosts": 2,
                    "dhcp": False,
                    "management": True,
                    "ports": 1,
                },
            ],
        },
        {
            "name": "remote",
            "vlans": [{"id": 10, "name": "users", "hosts": 20, "ports": 24}],
        },
    ],
    "links": [{"sites": ["main", "remote"]}],
}


@pytest.fixture
def raw():
    """The base description as plain data, safe to modify."""
    return copy.deepcopy(BASE)


@pytest.fixture
def lab(raw):
    return parse_network(raw)


@pytest.fixture
def examples():
    """Directory with the example network files."""
    return Path(__file__).parent.parent / "examples"
