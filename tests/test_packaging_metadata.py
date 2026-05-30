from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _requirements() -> list[str]:
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def test_package_data_includes_templates() -> None:
    package_data = _pyproject()["tool"]["setuptools"]["package-data"]

    assert "data/*.csv" in package_data["post_trip_summary"]
    assert "templates/*.html" in package_data["post_trip_summary"]


def test_requirements_txt_mirrors_runtime_dependencies() -> None:
    dependencies = set(_pyproject()["project"]["dependencies"])

    assert set(_requirements()) == dependencies
    assert {"numpy>=1.23", "scipy>=1.10"} <= dependencies


def test_integration_pytest_marker_is_registered() -> None:
    markers = _pyproject()["tool"]["pytest"]["ini_options"]["markers"]

    assert any(marker.startswith("integration:") for marker in markers)
