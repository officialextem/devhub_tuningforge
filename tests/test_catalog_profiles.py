from pathlib import Path

from core.catalog import load_catalog
from core.profiles import load_profiles


ROOT = Path(__file__).resolve().parent.parent


def test_catalog_loads_required_fields() -> None:
    packages = load_catalog(ROOT / "packages" / "catalog.json")

    assert packages
    assert all(package.id for package in packages)
    assert all(package.winget_id for package in packages)


def test_profiles_reference_known_packages() -> None:
    packages = load_catalog(ROOT / "packages" / "catalog.json")
    profiles = load_profiles(ROOT / "profiles", packages)

    package_ids = {package.id for package in packages}
    assert profiles
    for profile in profiles:
        assert set(profile.packages) <= package_ids


def test_catalog_contains_optional_extended_categories() -> None:
    packages = load_catalog(ROOT / "packages" / "catalog.json")
    categories = {package.category for package in packages}
    package_by_id = {package.id: package for package in packages}

    assert {"Gaming", "Grafikdesign/Creator", "Office/Finanzen", "Trading/Crypto"} <= categories
    assert "steam" in package_by_id
    assert "gimp" in package_by_id
    assert "libreoffice" in package_by_id
    assert "tradingview" in package_by_id
    assert not any(
        package.enabled_by_default
        for package in packages
        if package.category in {"Gaming", "Grafikdesign/Creator", "Medien", "Office/Finanzen", "Trading/Crypto", "Produktivitaet/Kommunikation"}
    )


def test_existing_profiles_do_not_auto_select_new_optional_packages() -> None:
    packages = load_catalog(ROOT / "packages" / "catalog.json")
    profiles = load_profiles(ROOT / "profiles", packages)
    new_optional_ids = {
        package.id
        for package in packages
        if package.category in {"Gaming", "Grafikdesign/Creator", "Medien", "Office/Finanzen", "Trading/Crypto", "Produktivitaet/Kommunikation"}
    }

    for profile in profiles:
        assert not (set(profile.packages) & new_optional_ids)
