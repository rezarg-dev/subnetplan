# Verification checklist: single-site

## Before you start

1. Replace every `CHANGE-ME` in the configuration files with real secrets.
2. Generate the SSH host key on every device. It is not part of the configuration file:
   `crypto key generate rsa general-keys modulus 2048`

## Per device

### OFFICE-R1

- `show ip interface brief`
  - `Gi0/0.10`, `Gi0/0.20`, `Gi0/0.30` are `up/up` with the gateway addresses from the plan.
  - `Gi0/1` is `up/up` with 198.51.100.6.
- `show ip dhcp pool`
  - Pools `STAFF`, `GUESTS` exist.
- `show ip dhcp binding` after a client has been connected
  - The client has a lease from the range in the plan.
- `show ip route static`
  - `S* 0.0.0.0/0` via 198.51.100.5.
- `show ip nat translations` while a client pings an outside address
  - Inside local addresses from 192.168.10.0/24 are translated to 198.51.100.6.

### OFFICE-SW1

- `show vlan brief`
  - VLAN 10 `staff`, VLAN 20 `printers`, VLAN 30 `guests` exist
    and the access ports are in the VLANs listed below.
- `show interfaces trunk`
  - `Gi0/1` is trunking, allowed VLANs `10,20,30`.
- `show port-security`
  - Every secured port is listed with violation action `Restrict`.

| Ports | VLAN | Name |
| --- | --- | --- |
| Fa0/1-16 | 10 | staff |
| Fa0/17-20 | 20 | printers |
| Fa0/21-24 | 30 | guests |

## End-to-end tests

Connect a PC to an access port of VLAN 10 (staff) at site office. From that PC:

1. `ping 192.168.10.1` reaches its own gateway.
2. `ping 192.168.10.97` reaches VLAN 20 (routing between VLANs).
3. `ping 192.168.10.65` reaches VLAN 30 (routing between VLANs).
4. `ping 198.51.100.5` reaches the provider (default route and NAT).
