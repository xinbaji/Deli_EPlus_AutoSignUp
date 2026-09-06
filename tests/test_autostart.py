"""autostart：注册表开关（CI Windows runner 可写 HKCU）。"""

import sys

import pytest

from deli_eplus import autostart


def test_default_off_and_toggle_roundtrip(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable",
                        r"C:\App\Deli_EPlus_AutoSignUp.exe", raising=False)
    try:
        autostart.set_enabled(False)
        assert autostart.is_enabled() is False
        autostart.set_enabled(True)
        assert autostart.is_enabled() is True
        autostart.set_enabled(False)
        assert autostart.is_enabled() is False
    except PermissionError:
        pytest.skip("注册表不可写")
