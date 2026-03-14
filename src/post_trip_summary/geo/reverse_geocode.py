"""Offline reverse geocoding using reverse_geocoder library."""
import reverse_geocoder as rg


def reverse_geocode(lat: float, lon: float) -> dict:
    results = rg.search([(lat, lon)])
    if not results:
        return {"city": "", "country": "", "admin1": "", "admin2": ""}
    r = results[0]
    return {"city": r.get("name", ""), "country": r.get("cc", ""), "admin1": r.get("admin1", ""), "admin2": r.get("admin2", "")}


def reverse_geocode_batch(coords: list[tuple[float, float]]) -> list[dict]:
    if not coords:
        return []
    results = rg.search(coords)
    return [{"city": r.get("name", ""), "country": r.get("cc", ""), "admin1": r.get("admin1", ""), "admin2": r.get("admin2", "")} for r in results]
