"""Command line interface."""

from __future__ import annotations

import argparse
import sys

from subnetplan import __version__
from subnetplan.calc import SubnetError, address_type, describe, legacy_class, split_binary


def _explain(args: argparse.Namespace) -> int:
    info = describe(" ".join(args.address))
    prefix = info.prefix

    rows = [
        ("Address", f"{info.address}/{prefix}"),
        ("Netmask", str(info.netmask)),
        ("Wildcard", str(info.wildcard)),
        ("Network", str(info.network)),
        ("Broadcast", str(info.broadcast) if info.broadcast else "none"),
        ("First host", str(info.first_host)),
        ("Last host", str(info.last_host)),
        ("Usable hosts", str(info.usable_hosts)),
        ("Type", f"{address_type(info.address)}, class {legacy_class(info.address)}"),
        ("This is", f"a {info.role}"),
    ]
    for label, value in rows:
        print(f"{label:<14}{value}")

    print()
    print("Binary (network bits | host bits)")
    binary = [
        ("Address", info.address),
        ("Netmask", info.netmask),
        ("Network", info.network.network_address),
    ]
    if info.broadcast:
        binary.append(("Broadcast", info.broadcast))
    for label, address in binary:
        print(f"{label:<14}{split_binary(address, prefix)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subnetplan",
        description="Plan IPv4 addressing for a multi-site network "
        "and generate Cisco IOS configuration for it.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    explain = commands.add_parser(
        "explain",
        help="show everything about one address and its subnet",
        description="Accepts 10.1.2.77/26, 10.1.2.77/255.255.255.192 or 10.1.2.77 255.255.255.192.",
    )
    explain.add_argument("address", nargs="+", metavar="ADDRESS")
    explain.set_defaults(run=_explain)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except SubnetError as error:
        print(f"subnetplan: {error}", file=sys.stderr)
        return 2
