"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from subnetplan import __version__
from subnetplan.calc import SubnetError, address_type, describe, legacy_class, split_binary
from subnetplan.export import to_csv, to_json, to_markdown
from subnetplan.ios.device import render_all
from subnetplan.loader import ConfigError, load
from subnetplan.plan import Plan, build_plan
from subnetplan.report import render_plan
from subnetplan.topology import to_topology
from subnetplan.validate import validate
from subnetplan.verify import render_checklist
from subnetplan.vlsm import AllocationError

_FORMATS = {
    "table": render_plan,
    "markdown": to_markdown,
    "json": to_json,
    "csv": to_csv,
}


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


def _load_plan(path: str) -> Plan:
    return build_plan(validate(load(path)))


def _plan(args: argparse.Namespace) -> int:
    sys.stdout.write(_FORMATS[args.format](_load_plan(args.file)))
    return 0


def _build(args: argparse.Namespace) -> int:
    plan = _load_plan(args.file)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    files = render_all(plan)
    files["plan.md"] = to_markdown(plan)
    files["plan.json"] = to_json(plan)
    files["VERIFY.md"] = render_checklist(plan)
    files["topology.json"] = json.dumps(to_topology(plan), indent=2) + "\n"

    for name, content in sorted(files.items()):
        (out / name).write_text(content, encoding="utf-8")
        print(f"wrote {out / name}")
    return 0


def _check(args: argparse.Namespace) -> int:
    plan = _load_plan(args.file)
    devices = 2 * len(plan.sites)
    print(
        f"{args.file}: ok ({len(plan.sites)} sites, {devices} devices, "
        f"{sum(len(site.vlans) for site in plan.sites)} VLANs, {len(plan.links)} WAN links)"
    )
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

    plan = commands.add_parser("plan", help="print the addressing plan for a network file")
    plan.add_argument("file", metavar="FILE")
    plan.add_argument(
        "--format", choices=sorted(_FORMATS), default="table", help="output format (default: table)"
    )
    plan.set_defaults(run=_plan)

    build = commands.add_parser(
        "build", help="write the device configurations and the plan to a directory"
    )
    build.add_argument("file", metavar="FILE")
    build.add_argument("--out", "-o", default="build", metavar="DIR", help="default: build")
    build.set_defaults(run=_build)

    check = commands.add_parser("check", help="validate a network file without writing anything")
    check.add_argument("file", metavar="FILE")
    check.set_defaults(run=_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except SubnetError as error:
        print(f"subnetplan: {error}", file=sys.stderr)
        return 2
    except ConfigError as error:
        print(f"subnetplan: {len(error.problems)} problem(s) in the network file:", file=sys.stderr)
        for problem in error.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2
    except AllocationError as error:
        print(f"subnetplan: {error}", file=sys.stderr)
        return 2
