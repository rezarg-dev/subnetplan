# subnetplan

[![CI](https://github.com/rezarg-dev/subnetplan/actions/workflows/ci.yml/badge.svg)](https://github.com/rezarg-dev/subnetplan/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)
![License](https://img.shields.io/badge/license-MIT-blue)

Describe a multi-site network in a short file, and get back

- an **addressing plan** worked out with VLSM, where every site is one
  summarisable block, and
- a **Cisco IOS configuration** for the router and the access switch of every
  site: VLANs, trunks, inter-VLAN routing, DHCP, OSPF, NAT, port security and
  SSH-only management.

It also has a subnet calculator that shows its work in binary.

No dependencies outside the Python standard library.

```
$ subnetplan plan examples/acme.toml
Network acme   block 10.20.0.0/21

Site hq   summary 10.20.0.0/23   router HQ-R1 (id 1.1.1.1)   switch HQ-SW1
  VLAN  Name         Hosts  Subnet          Mask             Gateway      DHCP range               Usable
  ----  -----------  -----  --------------  ---------------  -----------  -----------------------  ------
  10    staff        180    10.20.0.0/24    255.255.255.0    10.20.0.1    10.20.0.2 - 10.20.0.254  254
  20    engineering  90     10.20.1.0/25    255.255.255.128  10.20.1.1    10.20.1.2 - 10.20.1.126  126
  30    servers      20     10.20.1.128/27  255.255.255.224  10.20.1.129  -                        30
  99    management   5      10.20.1.160/28  255.255.255.240  10.20.1.161  -                        14

Site north   summary 10.20.2.0/25   router NORTH-R1 (id 2.2.2.2)   switch NORTH-SW1
  ...

WAN links   block 10.20.2.192/28
  Link           Subnet          Side A                      Side B
  -------------  --------------  --------------------------  ----------------------------
  hq - north     10.20.2.192/30  HQ-R1 Gi0/1 10.20.2.193     NORTH-R1 Gi0/1 10.20.2.194
  hq - south     10.20.2.196/30  HQ-R1 Se0/0/0 10.20.2.197   SOUTH-R1 Se0/0/0 10.20.2.198
  north - south  10.20.2.200/30  NORTH-R1 Gi0/2 10.20.2.201  SOUTH-R1 Gi0/1 10.20.2.202

Summary
  Hosts requested      408
  Addresses allocated  720 of 2048 (35%)
  Free blocks          10.20.2.208/28, 10.20.2.224/27, 10.20.3.0/24, 10.20.4.0/22
```

## Why

Subnetting a network by hand is a standard exercise, and doing it once is
worth it. Doing it for three sites, then typing forty subnet masks, wildcard
masks and gateway addresses into six devices without a single typo is where
the mistakes happen: a `/27` mask on a `/26` subnet, an OSPF `network`
statement with a subnet mask instead of a wildcard, an access port left in
VLAN 1.

subnetplan keeps one description of the network and derives everything else
from it. The plan, the configurations and the verification checklist cannot
disagree with each other, because they come from the same data.

## Install

Python 3.11 or newer.

```bash
git clone https://github.com/rezarg-dev/subnetplan.git
cd subnetplan
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Commands

### `explain`: one address, taken apart

```
$ subnetplan explain 10.1.2.77/26
Address       10.1.2.77/26
Netmask       255.255.255.192
Wildcard      0.0.0.63
Network       10.1.2.64/26
Broadcast     10.1.2.127
First host    10.1.2.65
Last host     10.1.2.126
Usable hosts  62
Type          private (RFC 1918), class A
This is       a host address

Binary (network bits | host bits)
Address       00001010.00000001.00000010.01|001101
Netmask       11111111.11111111.11111111.11|000000
Network       00001010.00000001.00000010.01|000000
Broadcast     00001010.00000001.00000010.01|111111
```

The mask can be given as a prefix length, as a dotted mask, or the way IOS
prints it: `subnetplan explain 10.1.2.77 255.255.255.192`.

### `plan`: the addressing plan

```bash
subnetplan plan examples/acme.toml                     # table, as shown above
subnetplan plan examples/acme.toml --format markdown   # for documentation
subnetplan plan examples/acme.toml --format csv        # for a spreadsheet
subnetplan plan examples/acme.toml --format json       # for other tools
```

### `build`: configurations and documentation

```
$ subnetplan build examples/acme.toml --out examples/acme
wrote examples/acme/HQ-R1.cfg
wrote examples/acme/HQ-SW1.cfg
wrote examples/acme/NORTH-R1.cfg
wrote examples/acme/NORTH-SW1.cfg
wrote examples/acme/SOUTH-R1.cfg
wrote examples/acme/SOUTH-SW1.cfg
wrote examples/acme/VERIFY.md
wrote examples/acme/plan.json
wrote examples/acme/plan.md
wrote examples/acme/topology.json
```

| File | Content |
| --- | --- |
| `<DEVICE>.cfg` | Configuration to paste into the device in global configuration mode |
| `plan.md`, `plan.json` | The addressing plan as a document and as data |
| `VERIFY.md` | Which `show` commands to run on which device, what they must display, and a sequence of pings from the inside out |
| `topology.json` | Devices and cables as nodes and links, for drawing a diagram |

The output for both examples is checked in:
[examples/acme](examples/acme) and [examples/single-site](examples/single-site).

### `check`: validate without writing

```
$ subnetplan check examples/acme.toml
examples/acme.toml: ok (3 sites, 6 devices, 9 VLANs, 3 WAN links)
```

All problems are reported at once, each with the place it was found:

```
$ subnetplan check broken.toml
subnetplan: 3 problem(s) in the network file:
  - sites[0].name: 'Head Office' must start with a letter and contain only lower-case letters, digits and hyphens (at most 20 characters)
  - sites[0].vlans[0].id: VLAN 1 is reserved on Cisco switches
  - sites[0].vlans[0].hosts: must be at least 1
```

Every command exits with status 2 if the input is invalid, so `check` can
guard a pipeline.

## The network file

A TOML file. [examples/acme.toml](examples/acme.toml) is a complete,
commented example.

```toml
name = "acme"
block = "10.20.0.0/21"          # everything is carved out of this
domain = "acme.example"
dns_servers = ["9.9.9.9"]
native_vlan = 999               # untagged VLAN on trunks, carries no hosts

[[sites]]
name = "hq"

[sites.internet]                # at most one site: it does NAT for all
interface = "GigabitEthernet0/2"
address = "203.0.113.2/30"
gateway = "203.0.113.1"

[[sites.vlans]]
id = 10
name = "staff"
hosts = 180                     # end devices; the gateway is added on top
ports = 12                      # access ports on the switch
port_security = 2               # max MAC addresses per port

[[sites.vlans]]
id = 99
name = "management"
hosts = 5
dhcp = false
management = true               # the switch gets its address here

[[links]]
sites = ["hq", "north"]         # point-to-point link between two routers
```

| Key | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Name of the network |
| `block` | yes | Address block all subnets are taken from |
| `domain` | no | Domain name for devices and DHCP clients. Default `example.internal` |
| `dns_servers` | no | Handed out by DHCP |
| `native_vlan` | no | Native VLAN on trunks. Without it, trunks use the default VLAN 1 |
| `sites[].name` | yes | Lower-case name. `hq` becomes `HQ-R1` and `HQ-SW1` |
| `sites[].internet` | no | `interface`, `address` (with prefix) and `gateway` of the provider uplink |
| `sites[].vlans[].id`, `name`, `hosts` | yes | VLAN id, name and number of end devices |
| `sites[].vlans[].dhcp` | no | Whether the router serves DHCP for this VLAN. Default `true` |
| `sites[].vlans[].management` | no | Put the switch's management address in this VLAN. Default `false` |
| `sites[].vlans[].ports` | no | Number of access ports for this VLAN. Default `0` |
| `sites[].vlans[].port_security` | no | Enable port security with this many MAC addresses per port |
| `links[].sites` | no | Two site names |
| `hardware` | no | Interface names, see below |

The interface names default to a Cisco 2911 router and a 2960 switch. For
other models, override them:

```toml
[hardware]
router_lan = "GigabitEthernet0/0/0"
router_wan = ["GigabitEthernet0/0/1", "Serial0/1/0", "Serial0/1/1"]
switch_uplink = "GigabitEthernet1/0/1"
switch_access_prefix = "GigabitEthernet1/0/"
switch_access_ports = 48
switch_spare = []
```

## How addresses are allocated

Plain VLSM sorts all subnets by size and places them one after another. That
wastes nothing, but the subnets of one site end up scattered across the
block, and each of them needs its own route everywhere else.

subnetplan allocates in two levels:

1. Every site gets **one contiguous block**, just large enough for its VLANs.
   The WAN links share one more block.
2. The VLANs are placed inside their site's block, largest first.

The `hq` site above needs a /24, a /25, a /27 and a /28. That is 432
addresses, so it gets the /23 `10.20.0.0/23`, and the whole site can be
reached through that single prefix. The price is some unused space inside
each site block, which is also room for the site to grow without
renumbering.

Within a VLAN, the first usable address is the gateway. In the management
VLAN the second is the switch. DHCP hands out everything after that.

## What the configurations contain

Routers:

- A subinterface per VLAN on the trunk to the switch (router-on-a-stick),
  including one for the native VLAN so both ends of the trunk agree
- A DHCP pool per VLAN that asks for one, with the gateway excluded
- WAN interfaces. Both ends of a link always get the same interface type; a
  router that runs out of Ethernet ports falls back to serial for the next
  link
- Single-area OSPF with a fixed router id. All interfaces are passive except
  the WAN links, so no hellos are sent towards user ports
- On the edge router: the uplink, a static default route announced into OSPF,
  and NAT overload for the whole block

Switches:

- VLANs with names, and a trunk that carries only this site's VLANs
- Access ports with PortFast and BPDU guard, optionally port security with
  sticky MAC addresses
- Every unused port shut down
- A management address and default gateway

Both:

- Local user, SSH version 2 as the only remote access, session timeouts,
  encrypted passwords, a login banner

Secrets are never generated. The configurations contain the placeholder
`CHANGE-ME`, and `VERIFY.md` starts with the manual steps: replace the
placeholders, generate the SSH key, set the clock rate on serial links.

[docs/lab-guide.md](docs/lab-guide.md) walks through loading the `acme`
example into Cisco Packet Tracer.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

```
src/subnetplan/
  calc.py          subnet arithmetic behind `explain`
  vlsm.py          the allocator
  model.py         the network as described by the user
  loader.py        TOML -> model, with all type errors collected
  validate.py      does the description make sense as a network?
  interfaces.py    which router port each WAN link uses
  plan.py          model -> addressing plan
  report.py        plan as a terminal table
  export.py        plan as JSON, CSV, Markdown
  topology.py      plan as nodes and links
  verify.py        the verification checklist
  ios/             one module per configuration section, assembled in device.py
  cli.py           argument parsing
```

How it is tested:

- **Unit tests** for the arithmetic, the allocator, validation and each
  configuration section.
- **Randomised tests** for the allocator: a few thousand random requirement
  sets, each checked for the properties any valid result must have (inside
  the block, no overlaps, no gaps, large enough, not larger than needed).
- **Golden files**: the checked-in output of the examples is regenerated and
  compared byte for byte, so a change to a generator shows up in review as a
  diff of actual configuration files.

[docs/design.md](docs/design.md) explains the decisions behind the code.

## Limitations

- **IPv4 only.**
- **One router and one access switch per site.** No distribution layer, no
  redundant gateways, no EtherChannel.
- **OSPF in a single area.** The per-site summaries are computed and shown,
  but with one area there is no place to configure them.
- **The configurations are generated, not pushed.** Nothing here talks to a
  device.
- **No ACLs between VLANs.** Guests can reach servers unless you add
  filtering.

## License

[MIT](LICENSE)
