from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from medium_mcp_server import __version__


def test_package_version_is_consistent() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert data["project"]["version"] == __version__


def test_packaging_metadata_has_release_essentials() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data["project"]

    assert project["name"] == "medium-mcp-server"
    assert project["readme"] == "README.md"
    assert project["requires-python"] == ">=3.10"
    assert project["scripts"]["medium-mcp-server"] == "medium_mcp_server.__main__:main"
    assert "release" in project["optional-dependencies"]
    assert "build>=1.2.2" in project["optional-dependencies"]["release"]
    assert "twine>=6.1.0" in project["optional-dependencies"]["release"]

    urls = project["urls"]
    assert urls["Repository"] == "https://github.com/sheikh-mohammad/medium-mcp-server"
