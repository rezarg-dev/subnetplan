"""Variable length subnet masking: carve a block into subnets of different sizes."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, summarize_address_range

from subnetplan.calc import prefix_for_hosts


class AllocationError(ValueError):
    """The requested subnets do not fit into the block."""


@dataclass(frozen=True)
class Request:
    name: str
    hosts: int

    @property
    def prefix(self) -> int:
        return prefix_for_hosts(self.hosts)


@dataclass(frozen=True)
class Allocation:
    name: str
    network: IPv4Network


def addresses_needed(prefixes: list[int]) -> int:
    return sum(2 ** (32 - prefix) for prefix in prefixes)


def smallest_block_prefix(prefixes: list[int]) -> int:
    """Prefix length of the smallest block that can hold subnets of these sizes.

    When subnets are placed largest first, every subnet starts on a multiple
    of its own size, so no address is lost to alignment. The block therefore
    only has to be the next power of two above the sum of the sizes.
    """
    needed = addresses_needed(prefixes)
    if needed == 0:
        raise AllocationError("nothing to allocate")
    if needed > 2**32:
        raise AllocationError("the requested subnets exceed the IPv4 address space")
    return 32 - (needed - 1).bit_length()


def place(block: IPv4Network, items: list[tuple[str, int]]) -> list[Allocation]:
    """Places subnets with the given prefix lengths into `block`.

    Largest subnets go first, which is what makes VLSM gap-free. Subnets of
    equal size keep the order they were given in. The result is in address
    order.
    """
    for name, prefix in items:
        if prefix < block.prefixlen:
            raise AllocationError(
                f"{name} needs a /{prefix}, which is larger than the whole block {block}"
            )

    ordered = sorted(items, key=lambda item: item[1])  # stable: ties keep input order
    cursor = int(block.network_address)
    end = int(block.broadcast_address) + 1
    allocations = []

    for name, prefix in ordered:
        size = 2 ** (32 - prefix)
        if cursor + size > end:
            needed = smallest_block_prefix([p for _, p in items])
            raise AllocationError(
                f"{block} is too small: {addresses_needed([p for _, p in items])} addresses "
                f"are needed, which takes at least a /{needed}"
            )
        allocations.append(Allocation(name, IPv4Network((cursor, prefix))))
        cursor += size

    return allocations


def allocate(block: IPv4Network, requests: list[Request]) -> list[Allocation]:
    """Gives every request the smallest subnet of `block` that fits its hosts."""
    return place(block, [(request.name, request.prefix) for request in requests])


def free_blocks(block: IPv4Network, used: list[IPv4Network]) -> list[IPv4Network]:
    """The parts of `block` not covered by `used`, as the fewest possible networks."""
    free = []
    cursor = int(block.network_address)

    for network in sorted(used):
        start = int(network.network_address)
        if start > cursor:
            free.extend(summarize_address_range(IPv4Address(cursor), IPv4Address(start - 1)))
        cursor = max(cursor, int(network.broadcast_address) + 1)

    end = int(block.broadcast_address)
    if cursor <= end:
        free.extend(summarize_address_range(IPv4Address(cursor), IPv4Address(end)))
    return free
