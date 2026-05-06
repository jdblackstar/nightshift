import pytest

from nightshift.cli import main


HELP_COMMANDS = [
    (["--help"], "Common commands:"),
    (["init", "--help"], "Example:"),
    (["repo", "--help"], "Example:"),
    (["repo", "init", "--help"], "Example:"),
    (["repos", "--help"], "Examples:"),
    (["repos", "add", "--help"], "Example:"),
    (["repos", "list", "--help"], "Example:"),
    (["repos", "remove", "--help"], "Example:"),
    (["repos", "enable", "--help"], "Example:"),
    (["repos", "disable", "--help"], "Example:"),
    (["context", "--help"], "Example:"),
    (["config", "--help"], "Example:"),
    (["config", "view", "--help"], "Example:"),
    (["doctor", "--help"], "Examples:"),
    (["dashboard", "--help"], "Example:"),
]


@pytest.mark.parametrize(("argv", "expected"), HELP_COMMANDS)
def test_cli_help_includes_command_guidance(
    argv: list[str], expected: str, capsys
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(argv)

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert expected in output
    assert "usage:" in output
