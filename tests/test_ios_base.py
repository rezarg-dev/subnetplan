from subnetplan.ios import base


def test_identity(lab):
    assert base.identity("MAIN-R1", lab) == [
        "service password-encryption",
        "no ip domain-lookup",
        "hostname MAIN-R1",
        "ip domain-name lab.example",
        "enable secret CHANGE-ME",
        "username admin privilege 15 secret CHANGE-ME",
    ]


def test_header_names_the_device_and_warns_about_placeholders(lab):
    header = base.header("MAIN-R1", lab)
    assert all(line.startswith("!") for line in header)
    assert "! MAIN-R1" in header
    assert any("CHANGE-ME" in line for line in header)


def test_remote_access_is_ssh_only_with_local_accounts():
    lines = base.access(vty_last=4)
    vty = lines[lines.index("line vty 0 4") :]

    assert " transport input ssh" in vty
    assert " login local" in vty
    assert "ip ssh version 2" in lines
    assert not any("telnet" in line for line in lines)
    assert not any(line.strip().startswith("password") for line in lines)


def test_switches_have_sixteen_vty_lines():
    assert "line vty 0 15" in base.access(vty_last=15)


def test_banner_delimiter_does_not_appear_in_the_text():
    (banner,) = [line for line in base.access(4) if line.startswith("banner motd")]
    assert banner.count("#") == 2
