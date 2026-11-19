# Lab guide: the acme example in Packet Tracer

This walks through building the network from
[examples/acme.toml](../examples/acme.toml) in Cisco Packet Tracer, using
the generated files in [examples/acme](../examples/acme).

## 1. Devices

| Device | Model | Note |
| --- | --- | --- |
| HQ-R1, NORTH-R1, SOUTH-R1 | 2911 | HQ-R1 and SOUTH-R1 need an HWIC-2T module for the serial link |
| HQ-SW1, NORTH-SW1, SOUTH-SW1 | 2960-24TT | |
| ISP | 2911 | Stands in for the provider |
| A few PCs | PC-PT | At least one per site |

To add the HWIC-2T: open the router, go to the *Physical* tab, switch the
router off, drag the module into a free slot and switch it on again. The
serial ports appear as `Serial0/0/0` and `Serial0/0/1`.

## 2. Cabling

The WAN table of `subnetplan plan examples/acme.toml` is the cabling list.

| From | To | Cable |
| --- | --- | --- |
| HQ-R1 Gi0/0 | HQ-SW1 Gi0/1 | Straight-through |
| NORTH-R1 Gi0/0 | NORTH-SW1 Gi0/1 | Straight-through |
| SOUTH-R1 Gi0/0 | SOUTH-SW1 Gi0/1 | Straight-through |
| HQ-R1 Gi0/1 | NORTH-R1 Gi0/1 | Crossover |
| HQ-R1 Se0/0/0 | SOUTH-R1 Se0/0/0 | Serial DCE |
| NORTH-R1 Gi0/2 | SOUTH-R1 Gi0/1 | Crossover |
| HQ-R1 Gi0/2 | ISP Gi0/0 | Crossover |
| PCs | Switch ports from the table in `VERIFY.md` | Straight-through |

With the *Serial DCE* cable, the router you click first gets the DCE end.
Click HQ-R1 first and remember it for step 4.

## 3. The provider

The ISP router is not part of the generated network. It needs one address
and nothing else, because NAT hides everything behind `203.0.113.2`:

```
enable
configure terminal
hostname ISP
interface GigabitEthernet0/0
 ip address 203.0.113.1 255.255.255.252
 no shutdown
end
```

## 4. Loading the configurations

For each of the six devices:

1. Open the device and go to the *CLI* tab. Answer `no` if it asks about the
   initial configuration dialog.
2. Enter global configuration mode:
   ```
   enable
   configure terminal
   ```
3. Open the matching `.cfg` file, replace both `CHANGE-ME` with a password,
   copy everything and paste it into the CLI.
4. The file ends with `end`, which leaves you in privileged mode. Generate
   the SSH key and save:
   ```
   configure terminal
   crypto key generate rsa general-keys modulus 2048
   end
   copy running-config startup-config
   ```

If Packet Tracer does not accept the options of the key command, enter
`crypto key generate rsa` on its own and answer `2048` when it asks for the
modulus.

On HQ-R1, which has the DCE end of the serial cable, also set the clock:

```
configure terminal
interface Serial0/0/0
 clock rate 128000
end
```

Packet Tracer implements a subset of IOS. If it answers a pasted line with
`% Invalid input detected`, note the line and carry on; the remaining lines
are still applied.

Give the links half a minute. Switch ports with PortFast come up at once,
the trunks and OSPF take a little longer.

## 5. Clients

Set the PCs to DHCP (*Desktop* → *IP Configuration* → *DHCP*). A PC on a
`staff` port at HQ should get an address between `10.20.0.2` and
`10.20.0.254` with gateway `10.20.0.1`.

Devices in VLANs without DHCP (`servers`, `management`) need a static
address from their subnet and the gateway from the plan.

## 6. Verification

Work through [examples/acme/VERIFY.md](../examples/acme/VERIFY.md). It lists
the `show` commands per device with the expected result, and ends with a
sequence of pings that tests one more piece of the network at each step:
own gateway, another VLAN, another site, the provider.

If a step fails, the ones before it tell you where to look:

| Fails | While this works | Look at |
| --- | --- | --- |
| Ping to own gateway | – | Access port VLAN (`show vlan brief`), trunk (`show interfaces trunk`), subinterface |
| Ping to another VLAN | Own gateway | The other subinterface, `encapsulation dot1Q` id |
| Ping to another site | Other VLANs | `show ip ospf neighbor`, WAN interface state, clock rate on the serial link |
| Ping to the provider | Other sites | `show ip route` for the default route, `show ip nat translations` |

## 7. Things to try

- **Redundancy.** The three sites form a triangle. Shut down `Gi0/1` on
  HQ-R1 and run `show ip route ospf` on NORTH-R1: the routes to HQ now point
  to SOUTH-R1. Pings between the sites keep working.
- **Port security.** `staff` ports allow two MAC addresses. Connect a small
  switch with three PCs to one of them and watch
  `show port-security interface Fa0/1` count violations while the first two
  PCs keep working.
- **BPDU guard.** Connect a switch to an access port. The port goes into
  `err-disabled` as soon as the first BPDU arrives.
- **NAT.** Ping `203.0.113.1` from PCs at two different sites and look at
  `show ip nat translations` on HQ-R1: both appear with the same outside
  address.
