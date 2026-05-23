from post_trip_summary.geo.airports import resolve_airport_candidate


def test_bundled_airport_seed_has_broad_travel_coverage():
    from post_trip_summary.geo.airports import load_airports

    airports = load_airports()
    iata_codes = {airport.iata_code for airport in airports}

    assert len(airports) >= 1000
    for code in ("AKL", "CMH", "CUN", "DFW", "HNL", "LHR", "NRT"):
        assert code in iata_codes


def test_resolve_airport_candidate_finds_cmh_for_airport_context():
    candidate = resolve_airport_candidate(
        39.99786388888889,
        -82.88245277777777,
        {"is_airport": True},
    )

    assert candidate is not None
    assert candidate["display_name"] == "John Glenn Columbus International Airport (CMH)"
    assert candidate["iata_code"] == "CMH"
    assert candidate["distance_m"] < 1500


def test_resolve_airport_candidate_ignores_distant_airport_without_context_signal():
    candidate = resolve_airport_candidate(
        39.9600,
        -82.9900,
        {"is_airport": False},
    )

    assert candidate is None
