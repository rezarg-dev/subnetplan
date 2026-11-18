"""Reads a network description from a TOML file."""

from __future__ import annotations

import tomllib
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from pathlib import Path
from typing import Any

from subnetplan.model import Hardware, Internet, Link, Network, Site, Vlan


class ConfigError(ValueError):
    """The network description is unusable. Carries every problem found."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


class _Reader:
    """Pulls typed values out of parsed TOML and collects what is wrong.

    Problems are collected instead of raised one at a time, so the user sees
    everything that needs fixing in a single run. Each message starts with
    the location of the value, e.g. "sites[1].vlans[0].hosts".
    """

    def __init__(self) -> None:
        self.problems: list[str] = []

    def error(self, where: str, message: str) -> None:
        self.problems.append(f"{where}: {message}")

    def table(self, value: Any, where: str, allowed: set[str]) -> dict[str, Any]:
        if not isinstance(value, dict):
            self.error(where, "expected a table")
            return {}
        for key in sorted(set(value) - allowed):
            self.error(f"{where}.{key}" if where else key, "unknown key")
        return value

    def get(self, table: dict, key: str, where: str, kind: type, default: Any = ...) -> Any:
        path = f"{where}.{key}" if where else key
        if key not in table:
            if default is ...:
                self.error(path, "is required")
                return None
            return default
        value = table[key]
        # bool is a subclass of int in Python; "hosts = true" must not pass.
        if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
            names = {str: "a string", int: "an integer", bool: "true or false", list: "a list"}
            self.error(path, f"must be {names[kind]}")
            return None if default is ... else default
        return value

    def parse(self, text: Any, where: str, parser: type, what: str) -> Any:
        if text is None:
            return None
        try:
            return parser(text)
        except ValueError:
            self.error(where, f"{text!r} is not {what}")
            return None


def _vlan(reader: _Reader, raw: Any, where: str) -> Vlan | None:
    table = reader.table(
        raw, where, {"id", "name", "hosts", "dhcp", "management", "ports", "port_security"}
    )
    vlan_id = reader.get(table, "id", where, int)
    name = reader.get(table, "name", where, str)
    hosts = reader.get(table, "hosts", where, int)
    dhcp = reader.get(table, "dhcp", where, bool, True)
    management = reader.get(table, "management", where, bool, False)
    ports = reader.get(table, "ports", where, int, 0)
    port_security = reader.get(table, "port_security", where, int, None)
    if vlan_id is None or name is None or hosts is None:
        return None
    return Vlan(vlan_id, name, hosts, dhcp, management, ports, port_security)


def _internet(reader: _Reader, raw: Any, where: str) -> Internet | None:
    table = reader.table(raw, where, {"interface", "address", "gateway"})
    interface = reader.get(table, "interface", where, str)
    address = reader.parse(
        reader.get(table, "address", where, str),
        f"{where}.address",
        IPv4Interface,
        "an address with a prefix length, like 203.0.113.2/30",
    )
    gateway = reader.parse(
        reader.get(table, "gateway", where, str), f"{where}.gateway", IPv4Address, "an IPv4 address"
    )
    if interface is None or address is None or gateway is None:
        return None
    return Internet(interface, address, gateway)


def _site(reader: _Reader, raw: Any, where: str) -> Site | None:
    table = reader.table(raw, where, {"name", "vlans", "internet"})
    name = reader.get(table, "name", where, str)
    raw_vlans = reader.get(table, "vlans", where, list, [])
    vlans = [_vlan(reader, item, f"{where}.vlans[{i}]") for i, item in enumerate(raw_vlans)]
    internet = None
    if "internet" in table:
        internet = _internet(reader, table["internet"], f"{where}.internet")
    if name is None:
        return None
    return Site(name, tuple(v for v in vlans if v is not None), internet)


def _link(reader: _Reader, raw: Any, where: str) -> Link | None:
    table = reader.table(raw, where, {"sites"})
    ends = reader.get(table, "sites", where, list)
    if ends is None:
        return None
    if len(ends) != 2 or not all(isinstance(end, str) for end in ends):
        reader.error(f"{where}.sites", "must name exactly two sites")
        return None
    return Link(ends[0], ends[1])


def _hardware(reader: _Reader, raw: Any) -> Hardware:
    defaults = Hardware()
    table = reader.table(
        raw,
        "hardware",
        {
            "router_lan",
            "router_wan",
            "switch_uplink",
            "switch_access_prefix",
            "switch_access_ports",
            "switch_spare",
        },
    )

    def names(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        value = reader.get(table, key, "hardware", list, list(default))
        if not all(isinstance(item, str) for item in value):
            reader.error(f"hardware.{key}", "must be a list of interface names")
            return default
        return tuple(value)

    return Hardware(
        router_lan=reader.get(table, "router_lan", "hardware", str, defaults.router_lan),
        router_wan=names("router_wan", defaults.router_wan),
        switch_uplink=reader.get(table, "switch_uplink", "hardware", str, defaults.switch_uplink),
        switch_access_prefix=reader.get(
            table, "switch_access_prefix", "hardware", str, defaults.switch_access_prefix
        ),
        switch_access_ports=reader.get(
            table, "switch_access_ports", "hardware", int, defaults.switch_access_ports
        ),
        switch_spare=names("switch_spare", defaults.switch_spare),
    )


def parse_network(data: dict[str, Any]) -> Network:
    """Turns parsed TOML into a Network. Raises ConfigError listing all problems.

    This only checks that every value has the right shape. Whether the
    description makes sense as a network is the job of `validate`.
    """
    reader = _Reader()
    top = reader.table(
        data,
        "",
        {"name", "block", "domain", "dns_servers", "native_vlan", "sites", "links", "hardware"},
    )

    name = reader.get(top, "name", "", str)
    block = reader.parse(
        reader.get(top, "block", "", str), "block", IPv4Network, "a network like 10.20.0.0/21"
    )
    domain = reader.get(top, "domain", "", str, "example.internal")
    native_vlan = reader.get(top, "native_vlan", "", int, None)

    dns_servers = []
    for i, item in enumerate(reader.get(top, "dns_servers", "", list, [])):
        parsed = reader.parse(item, f"dns_servers[{i}]", IPv4Address, "an IPv4 address")
        if parsed is not None:
            dns_servers.append(parsed)

    raw_sites = reader.get(top, "sites", "", list)
    sites = [_site(reader, item, f"sites[{i}]") for i, item in enumerate(raw_sites or [])]
    raw_links = reader.get(top, "links", "", list, [])
    links = [_link(reader, item, f"links[{i}]") for i, item in enumerate(raw_links)]
    hardware = _hardware(reader, top["hardware"]) if "hardware" in top else Hardware()

    if reader.problems:
        raise ConfigError(reader.problems)

    return Network(
        name=name,
        block=block,
        sites=tuple(sites),
        links=tuple(links),
        domain=domain,
        dns_servers=tuple(dns_servers),
        native_vlan=native_vlan,
        hardware=hardware,
    )


def load(path: str | Path) -> Network:
    path = Path(path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as error:
        raise ConfigError([f"{path}: {error.strerror}"]) from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError([f"{path}: not valid TOML: {error}"]) from None
    return parse_network(data)
