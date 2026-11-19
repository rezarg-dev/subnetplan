# Addressing plan: single-site

Block: `192.168.10.0/24`

## Site office

Summary route `192.168.10.0/25`, router `OFFICE-R1` (router id 1.1.1.1), switch `OFFICE-SW1`.

| VLAN | Name | Hosts | Subnet | Mask | Gateway | DHCP |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | staff | 40 | `192.168.10.0/26` | 255.255.255.192 | 192.168.10.1 | 192.168.10.2 to 192.168.10.62 |
| 20 | printers | 6 | `192.168.10.96/28` | 255.255.255.240 | 192.168.10.97 | static |
| 30 | guests | 20 | `192.168.10.64/27` | 255.255.255.224 | 192.168.10.65 | 192.168.10.66 to 192.168.10.94 |

## Free space

`192.168.10.128/25`
