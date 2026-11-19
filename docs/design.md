# Design notes

Why the code is shaped the way it is.

## One description, several outputs

The pipeline has four stages, and each one has a single job:

```
network.toml --load--> Network --validate--> Network --plan--> Plan --render--> files
```

- **load** only checks shapes: is `hosts` an integer, is `block` a network.
- **validate** checks meaning: do the VLAN ids exist on a Cisco switch, are
  all sites connected, are there enough router ports.
- **plan** assigns addresses and interfaces. It is the only stage that makes
  decisions.
- **render** turns a plan into text. Renderers never compute an address;
  they only format what the plan contains.

The last point is what keeps the outputs consistent. The table, the JSON
export, six configuration files and the checklist are all views of the same
`Plan` object. A gateway address appears in a DHCP pool, on a router
subinterface, as a switch's default gateway and in a ping test, and it is
computed exactly once.

## Collecting errors instead of stopping at the first

A network file with five mistakes should take one run to fix, not five. Both
the loader and the validator append to a list of problems and raise once at
the end. Every message starts with the path of the offending value
(`sites[1].vlans[0].hosts`), so it can be found without reading the message
twice.

Unknown keys are errors. Silently ignoring `dns_server` (instead of
`dns_servers`) would produce a configuration without DNS and no hint why.

## The allocator

VLSM works when subnets are placed from largest to smallest. Each subnet
size is a power of two, and after placing only subnets of size ≥ *s*, the
next free address is a multiple of *s*. So a subnet of size *s* can start
right there, with no padding. Sorting is the whole algorithm; the rest is
bookkeeping.

A consequence used elsewhere: the smallest block that can hold a set of
subnets is the sum of their sizes rounded up to a power of two. That is how
the size of each site block is determined before any address is assigned.

The sort is stable, so subnets of equal size keep the order of the input
file. Adding a VLAN at the end of a site does not shuffle the addresses of
the existing VLANs of the same size.

### Two levels

See the README for the motivation. The implementation reuses the same
placement function twice: once with the site blocks (and the WAN block) as
items inside the network block, then once per site with its VLANs as items
inside the site block.

### Why randomised tests

The allocator is short, and its edge cases are easy to miss: blocks that do
not start at an octet boundary, a single subnet that fills the block, many
subnets of the same size. Instead of guessing more examples, the tests
generate thousands of random requirement sets and check properties that must
hold for every correct result:

- every subnet lies inside the block and has room for its hosts,
- no subnet is one size larger than it needs to be,
- no two subnets overlap, and there are no gaps between them,
- used and free space add up to exactly the block,
- a block one size smaller is always rejected.

The random generator is seeded, so a failure can be reproduced.

## Interfaces for WAN links

The first version handed out router ports in order: first link gets the
first free port on each side. With the default hardware that connected a
serial port on one router to an Ethernet port on the other as soon as one
router had fewer free Ethernet ports than its neighbour, which is what
happens to the router with the internet uplink.

Now a link gets the first interface *type* that still has a free port on
both routers. The same function runs during validation, so a topology that
cannot be cabled is reported as a problem in the network file and not as a
surprise in the lab.

## Configuration sections

Each function in `subnetplan/ios/` returns the lines of one section and
knows nothing about the others. `device.py` decides the order. That order
matters to IOS in a few places, and the tests pin those down:

- `encapsulation dot1Q` before `ip address` on a subinterface. IOS rejects an
  address on a subinterface without encapsulation.
- `switchport mode access` before `switchport port-security`. A port in
  dynamic mode refuses port security.
- `ip dhcp excluded-address` before the pools, so the gateway address is
  never offered to a client.
- Interfaces before the routing and NAT commands that name them.

## Golden files

The unit tests check sections. They would not notice two sections that are
each correct but wrong together, or a change that alters output nobody wrote
an assertion for. So the complete output of every example is checked in, and
a test regenerates it and compares.

When a generator is changed on purpose, the test fails, the files are
regenerated, and the pull request then contains the diff of the actual
configurations. Reviewing "this line was added to every router" is much
easier than reviewing the code that adds it.

## Choices that were considered and dropped

**YAML for the network file.** More familiar in network automation, but it
needs a third-party parser. TOML is in the standard library since Python
3.11 and has no implicit typing surprises (`no` is not a boolean).

**Jinja2 templates for the configurations.** Templates are the usual tool,
and for a fixed device type they read well. Here most lines are conditional
on the plan (NAT only on the edge, OSPF only with links, port security per
VLAN), and a template with that much logic is harder to test than plain
functions returning lists of lines.

**Generating secrets.** A generated password in a file invites committing it.
A placeholder that cannot be mistaken for a real value is safer.
