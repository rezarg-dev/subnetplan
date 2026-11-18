from ipaddress import IPv4Address, IPv4Network

import pytest

from subnetplan.calc import (
    SubnetError,
    address_type,
    describe,
    legacy_class,
    parse_interface,
    prefix_for_hosts,
    split_binary,
    to_binary,
    usable_hosts,
)


def test_describe_host_in_a_slash_26():
    info = describe("10.1.2.77/26")
    assert info.network == IPv4Network("10.1.2.64/26")
    assert str(info.netmask) == "255.255.255.192"
    assert str(info.wildcard) == "0.0.0.63"
    assert str(info.first_host) == "10.1.2.65"
    assert str(info.last_host) == "10.1.2.126"
    assert str(info.broadcast) == "10.1.2.127"
    assert info.usable_hosts == 62
    assert info.role == "host address"


def test_describe_recognises_network_and_broadcast_addresses():
    assert describe("192.168.1.0/24").role == "network address"
    assert describe("192.168.1.255/24").role == "broadcast address"
    assert describe("192.168.1.128/24").role == "host address"


@pytest.mark.parametrize(
    "text",
    ["172.16.5.9/255.255.240.0", "172.16.5.9 255.255.240.0", "172.16.5.9/20", "  172.16.5.9/20 "],
)
def test_mask_notations_are_equivalent(text):
    assert describe(text).network == IPv4Network("172.16.0.0/20")


def test_point_to_point_and_host_routes_have_no_broadcast():
    p2p = describe("10.0.0.1/31")
    assert (p2p.first_host, p2p.last_host) == (IPv4Address("10.0.0.0"), IPv4Address("10.0.0.1"))
    assert p2p.broadcast is None
    assert p2p.usable_hosts == 2
    assert p2p.role == "host address"

    host = describe("10.0.0.7/32")
    assert host.first_host == host.last_host == IPv4Address("10.0.0.7")
    assert host.broadcast is None
    assert host.usable_hosts == 1


@pytest.mark.parametrize(
    "text", ["", "10.1.2.3", "10.1.2/24", "10.1.2.3/33", "a.b.c.d/24", "1 2 3"]
)
def test_invalid_input_is_rejected(text):
    with pytest.raises(SubnetError):
        parse_interface(text)


@pytest.mark.parametrize(
    ("prefix", "hosts"),
    [(24, 254), (25, 126), (30, 2), (31, 2), (32, 1), (16, 65534), (0, 2**32 - 2)],
)
def test_usable_hosts(prefix, hosts):
    assert usable_hosts(prefix) == hosts


@pytest.mark.parametrize(
    ("hosts", "prefix"),
    [
        (1, 30),
        (2, 30),
        (3, 29),
        (6, 29),
        (7, 28),
        (62, 26),
        (63, 25),
        (126, 25),
        (127, 24),
        (254, 24),
        (255, 23),
    ],
)
def test_prefix_for_hosts_picks_the_smallest_subnet_that_fits(hosts, prefix):
    assert prefix_for_hosts(hosts) == prefix
    assert usable_hosts(prefix) >= hosts
    if prefix < 30:
        assert usable_hosts(prefix + 1) < hosts


def test_prefix_for_hosts_rejects_nonsense():
    with pytest.raises(SubnetError):
        prefix_for_hosts(0)
    with pytest.raises(SubnetError):
        prefix_for_hosts(2**32)


@pytest.mark.parametrize(
    ("address", "kind"),
    [
        ("10.255.0.1", "private (RFC 1918)"),
        ("172.31.255.254", "private (RFC 1918)"),
        ("172.32.0.1", "public"),
        ("192.168.0.1", "private (RFC 1918)"),
        ("169.254.10.10", "link-local (APIPA)"),
        ("100.64.0.1", "shared address space (RFC 6598)"),
        ("203.0.113.9", "documentation (RFC 5737)"),
        ("224.0.0.5", "multicast"),
        ("8.8.8.8", "public"),
    ],
)
def test_address_type(address, kind):
    assert address_type(IPv4Address(address)) == kind


@pytest.mark.parametrize(
    ("address", "letter"),
    [
        ("10.0.0.1", "A"),
        ("127.0.0.1", "A"),
        ("128.0.0.1", "B"),
        ("191.255.0.1", "B"),
        ("192.0.0.1", "C"),
        ("223.255.255.1", "C"),
        ("224.0.0.1", "D"),
        ("240.0.0.1", "E"),
    ],
)
def test_legacy_class(address, letter):
    assert legacy_class(IPv4Address(address)) == letter


def test_binary_rendering():
    address = IPv4Address("10.1.2.77")
    assert to_binary(address) == "00001010.00000001.00000010.01001101"
    assert split_binary(address, 26) == "00001010.00000001.00000010.01|001101"
    assert split_binary(address, 24) == "00001010.00000001.00000010|01001101"
    assert split_binary(address, 8) == "00001010|00000001.00000010.01001101"
    assert split_binary(address, 32) == "00001010.00000001.00000010.01001101|"
    assert split_binary(address, 0) == "|00001010.00000001.00000010.01001101"
