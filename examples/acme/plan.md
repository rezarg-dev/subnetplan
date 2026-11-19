# Addressing plan: acme

Block: `10.20.0.0/21`

## Site hq

Summary route `10.20.0.0/23`, router `HQ-R1` (router id 1.1.1.1), switch `HQ-SW1`.

| VLAN | Name | Hosts | Subnet | Mask | Gateway | DHCP |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | staff | 180 | `10.20.0.0/24` | 255.255.255.0 | 10.20.0.1 | 10.20.0.2 to 10.20.0.254 |
| 20 | engineering | 90 | `10.20.1.0/25` | 255.255.255.128 | 10.20.1.1 | 10.20.1.2 to 10.20.1.126 |
| 30 | servers | 20 | `10.20.1.128/27` | 255.255.255.224 | 10.20.1.129 | static |
| 99 | management | 5 | `10.20.1.160/28` | 255.255.255.240 | 10.20.1.161 | static |

## Site north

Summary route `10.20.2.0/25`, router `NORTH-R1` (router id 2.2.2.2), switch `NORTH-SW1`.

| VLAN | Name | Hosts | Subnet | Mask | Gateway | DHCP |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | staff | 50 | `10.20.2.0/26` | 255.255.255.192 | 10.20.2.1 | 10.20.2.2 to 10.20.2.62 |
| 40 | guests | 25 | `10.20.2.64/27` | 255.255.255.224 | 10.20.2.65 | 10.20.2.66 to 10.20.2.94 |
| 99 | management | 5 | `10.20.2.96/28` | 255.255.255.240 | 10.20.2.97 | static |

## Site south

Summary route `10.20.2.128/26`, router `SOUTH-R1` (router id 3.3.3.3), switch `SOUTH-SW1`.

| VLAN | Name | Hosts | Subnet | Mask | Gateway | DHCP |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | staff | 28 | `10.20.2.128/27` | 255.255.255.224 | 10.20.2.129 | 10.20.2.130 to 10.20.2.158 |
| 99 | management | 5 | `10.20.2.160/28` | 255.255.255.240 | 10.20.2.161 | static |

## WAN links

Taken from `10.20.2.192/28`.

| Link | Subnet | Side A | Side B |
| --- | --- | --- | --- |
| hq to north | `10.20.2.192/30` | HQ-R1 GigabitEthernet0/1 10.20.2.193 | NORTH-R1 GigabitEthernet0/1 10.20.2.194 |
| hq to south | `10.20.2.196/30` | HQ-R1 Serial0/0/0 10.20.2.197 | SOUTH-R1 Serial0/0/0 10.20.2.198 |
| north to south | `10.20.2.200/30` | NORTH-R1 GigabitEthernet0/2 10.20.2.201 | SOUTH-R1 GigabitEthernet0/1 10.20.2.202 |

## Free space

`10.20.2.208/28`, `10.20.2.224/27`, `10.20.3.0/24`, `10.20.4.0/22`
