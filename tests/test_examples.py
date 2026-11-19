"""The generated output of every example is checked in next to it.

These tests regenerate the output and compare it byte for byte. Any change
to a generator shows up as a diff of real configuration files in review,
instead of hiding behind assertions that still happen to pass.

After an intended change, refresh the files with:

    subnetplan build examples/<name>.toml --out examples/<name>
"""

from pathlib import Path

import pytest

from subnetplan.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"
NAMES = sorted(path.stem for path in EXAMPLES.glob("*.toml"))


@pytest.mark.parametrize("name", NAMES)
def test_checked_in_output_is_up_to_date(name, tmp_path, capsys):
    assert main(["build", str(EXAMPLES / f"{name}.toml"), "--out", str(tmp_path)]) == 0
    capsys.readouterr()

    expected = {path.name: path.read_text() for path in (EXAMPLES / name).iterdir()}
    actual = {path.name: path.read_text() for path in tmp_path.iterdir()}

    assert sorted(actual) == sorted(expected)
    for file_name in sorted(expected):
        assert actual[file_name] == expected[file_name], f"{name}/{file_name} is out of date"
