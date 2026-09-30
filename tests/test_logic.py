from app.indie import classify_indie
from app.importer import parse_letterboxd_csv
from app.tmdb import pick_search_result


def test_classify_indie_studio():
    assert classify_indie(
        production_companies=["A24"],
        genres=["Drama"],
        keywords=[],
    )


def test_classify_indie_keyword():
    assert classify_indie(
        production_companies=["Warner Bros. Pictures"],
        genres=["Drama"],
        keywords=["independent film"],
    )


def test_classify_festival():
    assert classify_indie(
        production_companies=["Unknown Studio"],
        genres=["Comedy"],
        keywords=["Sundance Film Festival"],
    )


def test_classify_mainstream():
    assert not classify_indie(
        production_companies=["Marvel Studios", "Walt Disney Pictures"],
        genres=["Action", "Adventure"],
        keywords=["superhero"],
    )


def test_parse_sample_csv():
    df = parse_letterboxd_csv("sample_data/letterboxd_ratings.csv")
    assert list(df.columns)[:4] == ["Username", "Movie Name", "Year", "Rating10"]
    assert "alice" in set(df["Username"])


def test_pick_search_prefers_exact_year():
    results = [
        {"title": "Dune", "release_date": "1984-12-14", "popularity": 90, "vote_count": 2000},
        {"title": "Dune", "release_date": "2021-10-22", "popularity": 40, "vote_count": 800},
    ]
    best = pick_search_result(results, "Dune", 2021)
    assert best is not None
    assert best["release_date"].startswith("2021")
