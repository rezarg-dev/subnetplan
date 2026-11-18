"""IPv4 subnet arithmetic: everything the `explain` command prints."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Interface, IPv4Network


class SubnetError(ValueError):
    """The text given is not a usable IPv4 address or network."""


# Checked in order, first match wins. Written out here instead of using
# ipaddress.is_private, whose meaning has changed between Python versions.
_SPECIAL_RANGES = [
    ("10.0.0.0/8", "private (RFC 1918)"),
    ("172.16.0.0/12", "private (RFC 1918)"),
    ("192.168.0.0/16", "private (RFC 1918)"),
    ("127.0.0.0/8", "loopback"),
    ("169.254.0.0/16", "link-local (APIPA)"),
    ("100.64.0.0/10", "shared address space (RFC 6598)"),
    ("192.0.2.0/24", "documentation (RFC 5737)"),
    ("198.51.100.0/24", "documentation (RFC 5737)"),
    ("203.0.113.0/24", "documentation (RFC 5737)"),
    ("0.0.0.0/8", "this network"),
    ("224.0.0.0/4", "multicast"),
    ("240.0.0.0/4", "reserved"),
]
_SPECIAL = [(IPv4Network(cidr), label) for cidr, label in _SPECIAL_RANGES]


def usable_hosts(prefix: int) -> int:
    """Number of addresses that can be assigned to hosts in a subnet."""
    if prefix == 32:
        return 1
    if prefix == 31:
        # RFC 3021: both addresses of a /31 are usable on a point-to-point link.
        return 2
    return 2 ** (32 - prefix) - 2


def prefix_for_hosts(hosts: int) -> int:
    """Longest prefix (smallest subnet) that still has room for `hosts` hosts.

    Never returns anything longer than /30: this is used for LAN segments,
    where a network and a broadcast address are always needed.
    """
    if hosts < 1:
        raise SubnetError("a subnet needs room for at least one host")
    for prefix in range(30, -1, -1):
        if usable_hosts(prefix) >= hosts:
            return prefix
    raise SubnetError(f"{hosts} hosts do not fit into the IPv4 address space")


def parse_interface(text: str) -> IPv4Interface:
    """Parses an address with its prefix length or mask.

    Accepted: "10.1.2.77/26", "10.1.2.77/255.255.255.192" and the way IOS
    prints it, "10.1.2.77 255.255.255.192".
    """
    parts = text.split()
    if len(parts) == 2:
        text = f"{parts[0]}/{parts[1]}"
    elif len(parts) == 1:
        text = parts[0]
    else:
        raise SubnetError(f"{text!r}: expected ADDRESS/PREFIX or ADDRESS MASK")

    if "/" not in text:
        raise SubnetError(f"{text!r}: prefix length or subnet mask is missing")
    try:
        return IPv4Interface(text)
    except ValueError:
        raise SubnetError(f"{text!r} is not a valid IPv4 address and prefix") from None


def address_type(address: IPv4Address) -> str:
    for network, label in _SPECIAL:
        if address in network:
            return label
    return "public"


def legacy_class(address: IPv4Address) -> str:
    """Classful category, still used in CCNA material and in IOS defaults."""
    first_octet = int(address) >> 24
    if first_octet < 128:
        return "A"
    if first_octet < 192:
        return "B"
    if first_octet < 224:
        return "C"
    if first_octet < 240:
        return "D"
    return "E"


def to_binary(address: IPv4Address) -> str:
    """Dotted binary, e.g. 00001010.00000001.00000010.01001101."""
    return ".".join(f"{octet:08b}" for octet in address.packed)


def split_binary(address: IPv4Address, prefix: int) -> str:
    """Dotted binary with a "|" between the network bits and the host bits."""
    bits = f"{int(address):032b}"
    out = []
    for index, bit in enumerate(bits):
        if index == prefix:
            out.append("|")
        elif index and index % 8 == 0:
            out.append(".")
        out.append(bit)
    if prefix == 32:
        out.append("|")
    return "".join(out)


@dataclass(frozen=True)
class SubnetInfo:
    address: IPv4Address
    network: IPv4Network
    first_host: IPv4Address
    last_host: IPv4Address
    # None for /31 and /32, which have no broadcast address.
    broadcast: IPv4Address | None

    @property
    def prefix(self) -> int:
        return self.network.prefixlen

    @property
    def netmask(self) -> IPv4Address:
        return self.network.netmask

    @property
    def wildcard(self) -> IPv4Address:
        return self.network.hostmask

    @property
    def usable_hosts(self) -> int:
        return usable_hosts(self.prefix)

    @property
    def role(self) -> str:
        """What the given address is within its subnet."""
        if self.prefix >= 31:
            return "host address"
        if self.address == self.network.network_address:
            return "network address"
        if self.address == self.broadcast:
            return "broadcast address"
        return "host address"


def describe(text: str) -> SubnetInfo:
    interface = parse_interface(text)
    network = interface.network

    if network.prefixlen >= 31:
        first, last, broadcast = network[0], network[-1], None
    else:
        first, last, broadcast = network[1], network[-2], network.broadcast_address

    return SubnetInfo(
        address=interface.ip,
        network=network,
        first_host=first,
        last_host=last,
        broadcast=broadcast,
    )
