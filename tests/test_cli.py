"""Basic tests for the Nightshift CLI."""

from nightshift.cli import NightshiftApp, main


def test_app_class_exists() -> None:
    """Verify the NightshiftApp class can be instantiated."""
    app = NightshiftApp()
    assert app.title == "Nightshift"
    assert app.sub_title == "Put unused AI subscription usage to work"


def test_main_is_callable() -> None:
    """Verify the main entry point is a callable function."""
    assert callable(main)
