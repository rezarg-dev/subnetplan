"""Randomised checks of the allocator.

Hand-picked examples only cover the cases someone thought of. These tests
throw a few thousand random requirement sets at the allocator and check the
properties every valid result must have. The seed is fixed, so a failure is
reproducible.
"""

import random
from ipaddress import IPv4Network

from subnetplan.calc import usable_hosts
from subnetplan.vlsm import (
    AllocationError,
    Request,
    addresses_needed,
    allocate,
    free_blocks,
    smallest_block_prefix,
)

ROUNDS = 2000


def random_requests(rng):
    count = rng.randint(1, 12)
    # Skewed towards small subnets, like real networks.
    return [Request(f"net{i}", int(rng.paretovariate(0.7))) for i in range(count)]


def test_allocations_are_valid_for_random_requirements():
    rng = random.Random(20240917)

    for _ in range(ROUNDS):
        requests = random_requests(rng)
        requests = [r for r in requests if r.hosts <= 60_000]
        if not requests:
            continue

        prefix = smallest_block_prefix([r.prefix for r in requests])
        block = IPv4Network(
            (rng.randrange(0, 2**32 - 2 ** (32 - prefix)) >> (32 - prefix) << (32 - prefix), prefix)
        )
        result = allocate(block, requests)
        by_name = {allocation.name: allocation.network for allocation in result}

        assert len(result) == len(requests)
        for request in requests:
            network = by_name[request.name]
            assert network.subnet_of(block)
            assert usable_hosts(network.prefixlen) >= request.hosts
            # Not wastefully large: the next smaller subnet would not fit.
            if network.prefixlen < 30:
                assert usable_hosts(network.prefixlen + 1) < request.hosts

        ordered = sorted(by_name.values())
        for left, right in zip(ordered, ordered[1:], strict=False):
            assert not left.overlaps(right)
            # Gap-free: each subnet starts where the previous one ended.
            assert int(right.network_address) == int(left.broadcast_address) + 1
        assert ordered[0].network_address == block.network_address

        # Used and free space together make up the block exactly.
        free = free_blocks(block, ordered)
        covered = sum(n.num_addresses for n in ordered) + sum(n.num_addresses for n in free)
        assert covered == block.num_addresses


def test_one_size_smaller_block_is_always_rejected():
    rng = random.Random(7)

    for _ in range(ROUNDS):
        requests = [r for r in random_requests(rng) if r.hosts <= 60_000]
        if not requests:
            continue
        prefix = smallest_block_prefix([r.prefix for r in requests])
        if prefix >= 30:
            continue

        too_small = IPv4Network(f"10.0.0.0/{prefix + 1}")
        assert addresses_needed([r.prefix for r in requests]) > too_small.num_addresses
        try:
            allocate(too_small, requests)
        except AllocationError:
            continue
        raise AssertionError(f"{requests} should not fit into {too_small}")
