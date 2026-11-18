from ipaddress import IPv4Network

import pytest

from subnetplan.vlsm import (
    AllocationError,
    Request,
    allocate,
    free_blocks,
    place,
    smallest_block_prefix,
)


def networks(allocations):
    return {allocation.name: str(allocation.network) for allocation in allocations}


def test_textbook_example():
    # The classic exercise: 192.168.1.0/24 for 100, 50, 25 and 10 hosts plus two links.
    result = allocate(
        IPv4Network("192.168.1.0/24"),
        [
            Request("link-1", 2),
            Request("sales", 50),
            Request("guests", 10),
            Request("engineering", 100),
            Request("link-2", 2),
            Request("support", 25),
        ],
    )
    assert networks(result) == {
        "engineering": "192.168.1.0/25",
        "sales": "192.168.1.128/26",
        "support": "192.168.1.192/27",
        "guests": "192.168.1.224/28",
        "link-1": "192.168.1.240/30",
        "link-2": "192.168.1.244/30",
    }


def test_result_is_in_address_order_and_equal_sizes_keep_input_order():
    result = allocate(
        IPv4Network("10.0.0.0/24"), [Request("b", 20), Request("a", 20), Request("big", 100)]
    )
    assert [allocation.name for allocation in result] == ["big", "b", "a"]


def test_a_block_can_be_filled_exactly():
    result = allocate(IPv4Network("10.0.0.0/24"), [Request("a", 126), Request("b", 126)])
    assert networks(result) == {"a": "10.0.0.0/25", "b": "10.0.0.128/25"}


def test_too_small_block_says_what_would_be_enough():
    with pytest.raises(AllocationError, match=r"384 addresses are needed.*at least a /23"):
        allocate(IPv4Network("10.0.0.0/24"), [Request("a", 200), Request("b", 100)])


def test_single_request_larger_than_the_block():
    with pytest.raises(AllocationError, match="larger than the whole block"):
        allocate(IPv4Network("10.0.0.0/26"), [Request("a", 100)])


def test_block_that_does_not_start_at_zero():
    result = allocate(IPv4Network("172.16.8.0/22"), [Request("a", 300), Request("b", 60)])
    assert networks(result) == {"a": "172.16.8.0/23", "b": "172.16.10.0/26"}


@pytest.mark.parametrize(
    ("prefixes", "expected"),
    [([24], 24), ([24, 24], 23), ([25, 26, 27], 24), ([30], 30), ([24, 30], 23), ([30] * 5, 27)],
)
def test_smallest_block_prefix(prefixes, expected):
    assert smallest_block_prefix(prefixes) == expected
    # And the block of that size really is enough.
    block = IPv4Network(f"10.0.0.0/{expected}")
    place(block, [(str(index), prefix) for index, prefix in enumerate(prefixes)])


def test_free_blocks_lists_what_is_left():
    block = IPv4Network("10.0.0.0/24")
    used = [IPv4Network("10.0.0.0/25"), IPv4Network("10.0.0.128/27")]
    assert [str(n) for n in free_blocks(block, used)] == ["10.0.0.160/27", "10.0.0.192/26"]


def test_free_blocks_with_gaps_and_edges():
    block = IPv4Network("10.0.0.0/24")
    assert free_blocks(block, []) == [block]
    assert free_blocks(block, [block]) == []
    assert [str(n) for n in free_blocks(block, [IPv4Network("10.0.0.64/26")])] == [
        "10.0.0.0/26",
        "10.0.0.128/25",
    ]
