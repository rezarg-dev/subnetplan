# Verification checklist: acme

## Before you start

1. Replace every `CHANGE-ME` in the configuration files with real secrets.
2. Generate the SSH host key on every device. It is not part of the configuration file:
   `crypto key generate rsa general-keys modulus 2048`
3. Serial links (HQ-R1 - SOUTH-R1): set `clock rate 128000` on the interface that has the DCE end of the cable.

## Per device

### HQ-R1

- `show ip interface brief`
  - `Gi0/0.10`, `Gi0/0.20`, `Gi0/0.30`, `Gi0/0.99` are `up/up` with the gateway addresses from the plan.
  - `Gi0/1` is `up/up` with 10.20.2.193.
  - `Se0/0/0` is `up/up` with 10.20.2.197.
  - `Gi0/2` is `up/up` with 203.0.113.2.
- `show ip dhcp pool`
  - Pools `STAFF`, `ENGINEERING` exist.
- `show ip dhcp binding` after a client has been connected
  - The client has a lease from the range in the plan.
- `show ip ospf neighbor`
  - 2 neighbour(s) in state `FULL`: NORTH-R1 (2.2.2.2), SOUTH-R1 (3.3.3.3).
- `show ip route ospf`
  - 5 routes to the VLAN subnets of the other sites.
- `show ip route static`
  - `S* 0.0.0.0/0` via 203.0.113.1.
- `show ip nat translations` while a client pings an outside address
  - Inside local addresses from 10.20.0.0/21 are translated to 203.0.113.2.

### HQ-SW1

- `show vlan brief`
  - VLAN 10 `staff`, VLAN 20 `engineering`, VLAN 30 `servers`, VLAN 99 `management` exist
    and the access ports are in the VLANs listed below.
- `show interfaces trunk`
  - `Gi0/1` is trunking, allowed VLANs `10,20,30,99`, native VLAN 999.
- `show port-security`
  - Every secured port is listed with violation action `Restrict`.
- `show ip interface brief`
  - `Vlan99` is `up/up` with 10.20.1.162.

| Ports | VLAN | Name |
| --- | --- | --- |
| Fa0/1-12 | 10 | staff |
| Fa0/13-16 | 20 | engineering |
| Fa0/17-20 | 30 | servers |
| Fa0/21 | 99 | management |

### NORTH-R1

- `show ip interface brief`
  - `Gi0/0.10`, `Gi0/0.40`, `Gi0/0.99` are `up/up` with the gateway addresses from the plan.
  - `Gi0/1` is `up/up` with 10.20.2.194.
  - `Gi0/2` is `up/up` with 10.20.2.201.
- `show ip dhcp pool`
  - Pools `STAFF`, `GUESTS` exist.
- `show ip dhcp binding` after a client has been connected
  - The client has a lease from the range in the plan.
- `show ip ospf neighbor`
  - 2 neighbour(s) in state `FULL`: HQ-R1 (1.1.1.1), SOUTH-R1 (3.3.3.3).
- `show ip route ospf`
  - 6 routes to the VLAN subnets of the other sites.
  - A default route marked `O*E2`, learned from the edge router.

### NORTH-SW1

- `show vlan brief`
  - VLAN 10 `staff`, VLAN 40 `guests`, VLAN 99 `management` exist
    and the access ports are in the VLANs listed below.
- `show interfaces trunk`
  - `Gi0/1` is trunking, allowed VLANs `10,40,99`, native VLAN 999.
- `show port-security`
  - Every secured port is listed with violation action `Restrict`.
- `show ip interface brief`
  - `Vlan99` is `up/up` with 10.20.2.98.

| Ports | VLAN | Name |
| --- | --- | --- |
| Fa0/1-16 | 10 | staff |
| Fa0/17-20 | 40 | guests |
| Fa0/21 | 99 | management |

### SOUTH-R1

- `show ip interface brief`
  - `Gi0/0.10`, `Gi0/0.99` are `up/up` with the gateway addresses from the plan.
  - `Se0/0/0` is `up/up` with 10.20.2.198.
  - `Gi0/1` is `up/up` with 10.20.2.202.
- `show ip dhcp pool`
  - Pools `STAFF` exist.
- `show ip dhcp binding` after a client has been connected
  - The client has a lease from the range in the plan.
- `show ip ospf neighbor`
  - 2 neighbour(s) in state `FULL`: HQ-R1 (1.1.1.1), NORTH-R1 (2.2.2.2).
- `show ip route ospf`
  - 7 routes to the VLAN subnets of the other sites.
  - A default route marked `O*E2`, learned from the edge router.

### SOUTH-SW1

- `show vlan brief`
  - VLAN 10 `staff`, VLAN 99 `management` exist
    and the access ports are in the VLANs listed below.
- `show interfaces trunk`
  - `Gi0/1` is trunking, allowed VLANs `10,99`, native VLAN 999.
- `show port-security`
  - Every secured port is listed with violation action `Restrict`.
- `show ip interface brief`
  - `Vlan99` is `up/up` with 10.20.2.162.

| Ports | VLAN | Name |
| --- | --- | --- |
| Fa0/1-20 | 10 | staff |
| Fa0/21 | 99 | management |

## End-to-end tests

Connect a PC to an access port of VLAN 10 (staff) at site hq. From that PC:

1. `ping 10.20.0.1` reaches its own gateway.
2. `ping 10.20.1.1` reaches VLAN 20 (routing between VLANs).
3. `ping 10.20.1.129` reaches VLAN 30 (routing between VLANs).
4. `ping 10.20.1.161` reaches VLAN 99 (routing between VLANs).
5. `ping 10.20.2.1` reaches site north (OSPF across the WAN).
6. `ping 10.20.2.129` reaches site south (OSPF across the WAN).
7. `ping 203.0.113.1` reaches the provider (default route and NAT).

The WAN has more links than it needs to connect all sites. Shut down one WAN interface, wait for OSPF to converge and repeat the pings between sites: they must still succeed over the remaining links.
