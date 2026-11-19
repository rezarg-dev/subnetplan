from subnetplan.cli import main


def test_check_summarises_a_valid_file(capsys, examples):
    path = str(examples / "acme.toml")
    assert main(["check", path]) == 0
    assert capsys.readouterr().out == f"{path}: ok (3 sites, 6 devices, 9 VLANs, 3 WAN links)\n"


def test_check_fails_on_problems(capsys, tmp_path, examples):
    text = (
        (examples / "acme.toml")
        .read_text()
        .replace('sites = ["north", "south"]', 'sites = ["north", "west"]')
    )
    path = tmp_path / "typo.toml"
    path.write_text(text)

    assert main(["check", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "links[2]: there is no site named 'west'" in captured.err


def test_check_also_catches_a_block_that_is_too_small(capsys, tmp_path, examples):
    text = (examples / "acme.toml").read_text().replace("10.20.0.0/21", "10.20.0.0/24")
    path = tmp_path / "small.toml"
    path.write_text(text)
    assert main(["check", str(path)]) == 2
    assert "larger than the whole block" in capsys.readouterr().err
