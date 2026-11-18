from subnetplan.cli import main


def test_explain_prints_the_subnet_details(capsys):
    assert main(["explain", "10.1.2.77/26"]) == 0
    out = capsys.readouterr().out.splitlines()

    assert out[:10] == [
        "Address       10.1.2.77/26",
        "Netmask       255.255.255.192",
        "Wildcard      0.0.0.63",
        "Network       10.1.2.64/26",
        "Broadcast     10.1.2.127",
        "First host    10.1.2.65",
        "Last host     10.1.2.126",
        "Usable hosts  62",
        "Type          private (RFC 1918), class A",
        "This is       a host address",
    ]
    assert out[10] == ""
    assert out[11:] == [
        "Binary (network bits | host bits)",
        "Address       00001010.00000001.00000010.01|001101",
        "Netmask       11111111.11111111.11111111.11|000000",
        "Network       00001010.00000001.00000010.01|000000",
        "Broadcast     00001010.00000001.00000010.01|111111",
    ]


def test_explain_accepts_address_and_mask_as_two_arguments(capsys):
    assert main(["explain", "192.168.1.130", "255.255.255.128"]) == 0
    assert "Network       192.168.1.128/25" in capsys.readouterr().out


def test_explain_point_to_point_link_has_no_broadcast(capsys):
    assert main(["explain", "10.0.0.1/31"]) == 0
    out = capsys.readouterr().out
    assert "Broadcast     none" in out
    assert out.count("Broadcast") == 1


def test_explain_rejects_invalid_input(capsys):
    assert main(["explain", "300.1.1.1/24"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "subnetplan: '300.1.1.1/24' is not a valid IPv4 address and prefix\n"
