#!/usr/bin/env python3
"""Build a synthetic Letterboxd-style export for load and accuracy testing."""

from __future__ import annotations

import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sample_data" / "letterboxd_large.csv"

INDIE = [
    ("Moonlight", 2016),
    ("Lady Bird", 2017),
    ("The Grand Budapest Hotel", 2014),
    ("Everything Everywhere All at Once", 2022),
    ("Uncut Gems", 2019),
    ("The Witch", 2015),
    ("Hereditary", 2018),
    ("Past Lives", 2023),
    ("Aftersun", 2022),
    ("The Florida Project", 2017),
    ("The Banshees of Inisherin", 2022),
    ("Nomadland", 2020),
    ("Parasite", 2019),
    ("Whiplash", 2014),
    ("Ex Machina", 2014),
    ("Midsommar", 2019),
    ("Get Out", 2017),
    ("The Lighthouse", 2019),
    ("Portrait of a Lady on Fire", 2019),
    ("The Farewell", 2019),
    ("Minari", 2020),
    ("Manchester by the Sea", 2016),
    ("Moonrise Kingdom", 2012),
    ("Room", 2015),
    ("Little Women", 2019),
    ("Jojo Rabbit", 2019),
    ("The Worst Person in the World", 2021),
    ("Drive My Car", 2021),
    ("The Zone of Interest", 2023),
    ("Anatomy of a Fall", 2023),
    ("Poor Things", 2023),
    ("The Holdovers", 2023),
    ("All of Us Strangers", 2023),
    ("May December", 2023),
    ("Saltburn", 2023),
    ("Tár", 2022),
    ("The Fabelmans", 2022),
    ("The Green Knight", 2021),
    ("Pig", 2021),
    ("First Reformed", 2017),
    ("A Ghost Story", 2017),
    ("Swiss Army Man", 2016),
    ("The Lobster", 2015),
    ("Under the Skin", 2013),
    ("Her", 2013),
    ("Frances Ha", 2012),
    ("Beasts of the Southern Wild", 2012),
    ("Winter's Bone", 2010),
    ("The Wrestler", 2008),
    ("There Will Be Blood", 2007),
    ("No Country for Old Men", 2007),
    ("Pan's Labyrinth", 2006),
    ("Lost in Translation", 2003),
    ("Punch-Drunk Love", 2002),
    ("Mulholland Drive", 2001),
    ("Requiem for a Dream", 2000),
    ("Being John Malkovich", 1999),
    ("The Blair Witch Project", 1999),
    ("Boogie Nights", 1997),
    ("Fargo", 1996),
    ("Pulp Fiction", 1994),
    ("Clerks", 1994),
    ("Do the Right Thing", 1989),
    ("Eraserhead", 1977),
    ("Night of the Living Dead", 1968),
    ("Easy Rider", 1969),
    ("The Florida Project", 2017),
    ("CODA", 2021),
    ("Promising Young Woman", 2020),
    ("Sound of Metal", 2019),
    ("The Souvenir", 2019),
    ("Marriage Story", 2019),
    ("The Irishman", 2019),
    ("Once Upon a Time in Hollywood", 2019),
    ("Phantom Thread", 2017),
    ("Call Me by Your Name", 2017),
    ("The Shape of Water", 2017),
    ("A Ghost Story", 2017),
    ("The Killing of a Sacred Deer", 2017),
    ("Good Time", 2017),
    ("The Witch", 2015),
    ("It Follows", 2014),
    ("Boyhood", 2014),
    ("Her", 2013),
    ("Spring Breakers", 2012),
    ("Beasts of the Southern Wild", 2012),
    ("Drive", 2011),
    ("Martha Marcy May Marlene", 2011),
    ("Black Swan", 2010),
    ("A Serious Man", 2009),
    ("Synecdoche, New York", 2008),
    ("Juno", 2007),
    ("Little Miss Sunshine", 2006),
    ("Brokeback Mountain", 2005),
    ("Sideways", 2004),
    ("Lost in Translation", 2003),
    ("Donnie Darko", 2001),
    ("Requiem for a Dream", 2000),
    ("The Virgin Suicides", 1999),
    ("Rushmore", 1998),
    ("The Ice Storm", 1997),
    ("Welcome to the Dollhouse", 1995),
    ("Clerks", 1994),
    ("Reservoir Dogs", 1992),
    ("sex, lies, and videotape", 1989),
    ("Blue Velvet", 1986),
    ("Stranger Than Paradise", 1984),
    ("Eraserhead", 1977),
    ("The Texas Chain Saw Massacre", 1974),
    ("Mean Streets", 1973),
    ("Wanda", 1970),
    ("Night of the Living Dead", 1968),
    ("Persona", 1966),
    ("The 400 Blows", 1959),
    ("The Seventh Seal", 1957),
    ("Tokyo Story", 1953),
    ("Bicycle Thieves", 1948),
    ("After Hours", 1985),
    ("Dope", 2015),
    ("The Big Sick", 2017),
    ("Booksmart", 2019),
    ("The Farewell", 2019),
    ("Never Rarely Sometimes Always", 2020),
    ("The Worst Person in the World", 2021),
    ("After Yang", 2021),
    ("Petite Maman", 2021),
    ("Licorice Pizza", 2021),
    ("C'mon C'mon", 2021),
    ("Red Rocket", 2021),
    ("The Outfit", 2022),
    ("Aftersun", 2022),
    ("Women Talking", 2022),
    ("Living", 2022),
    ("The Wonder", 2022),
    ("Close", 2022),
    ("Decision to Leave", 2022),
    ("RRR", 2022),
    ("The Whale", 2022),
    ("A Thousand and One", 2023),
    ("Showing Up", 2022),
    ("Passages", 2023),
    ("Bottoms", 2023),
    ("How to Have Sex", 2023),
    ("The Taste of Things", 2023),
    ("Perfect Days", 2023),
    ("Fallen Leaves", 2023),
    ("The Beast", 2023),
    ("Priscilla", 2023),
    ("Origin", 2023),
    ("American Fiction", 2023),
    ("The Iron Claw", 2023),
    ("Society of the Snow", 2023),
    ("Monster", 2023),
    ("The Teachers' Lounge", 2023),
    ("The Zone of Interest", 2023),
    ("All Dirt Roads Taste of Salt", 2023),
    ("A Real Pain", 2024),
    ("Anora", 2024),
    ("The Substance", 2024),
    ("I Saw the TV Glow", 2024),
    ("Challengers", 2024),
    ("Civil War", 2024),
    ("Longlegs", 2024),
    ("Sing Sing", 2023),
    ("Thelma", 2024),
    ("Janet Planet", 2023),
    ("Good One", 2024),
    ("Dìdi", 2024),
    ("His Three Daughters", 2023),
    ("Hard Truths", 2024),
    ("Nickel Boys", 2024),
    ("The Brutalist", 2024),
    ("Septet: The Story of Hong Kong", 2020),
]

MAINSTREAM = [
    ("Dune", 2021),
    ("Dune: Part Two", 2024),
    ("The Batman", 2022),
    ("Avengers: Endgame", 2019),
    ("Avengers: Infinity War", 2018),
    ("The Avengers", 2012),
    ("Inception", 2010),
    ("The Dark Knight", 2008),
    ("The Dark Knight Rises", 2012),
    ("Batman Begins", 2005),
    ("Interstellar", 2014),
    ("Oppenheimer", 2023),
    ("Barbie", 2023),
    ("Spider-Man: No Way Home", 2021),
    ("Spider-Man: Across the Spider-Verse", 2023),
    ("Spider-Man: Into the Spider-Verse", 2018),
    ("Top Gun: Maverick", 2022),
    ("Avatar", 2009),
    ("Avatar: The Way of Water", 2022),
    ("Titanic", 1997),
    ("Jurassic Park", 1993),
    ("Star Wars", 1977),
    ("The Empire Strikes Back", 1980),
    ("Return of the Jedi", 1983),
    ("The Matrix", 1999),
    ("The Matrix Reloaded", 2003),
    ("Gladiator", 2000),
    ("Forrest Gump", 1994),
    ("The Lord of the Rings: The Fellowship of the Ring", 2001),
    ("The Lord of the Rings: The Two Towers", 2002),
    ("The Lord of the Rings: The Return of the King", 2003),
    ("Harry Potter and the Sorcerer's Stone", 2001),
    ("Harry Potter and the Prisoner of Azkaban", 2004),
    ("Iron Man", 2008),
    ("Black Panther", 2018),
    ("Guardians of the Galaxy", 2014),
    ("Thor: Ragnarok", 2017),
    ("Captain America: The Winter Soldier", 2014),
    ("Joker", 2019),
    ("Mad Max: Fury Road", 2015),
    ("Furiosa: A Mad Max Saga", 2024),
    ("La La Land", 2016),
    ("The Social Network", 2010),
    ("Gone Girl", 2014),
    ("Knives Out", 2019),
    ("Glass Onion", 2022),
    ("John Wick", 2014),
    ("John Wick: Chapter 4", 2023),
    ("Mission: Impossible - Fallout", 2018),
    ("Skyfall", 2012),
    ("Casino Royale", 2006),
    ("Deadpool", 2016),
    ("Wonder Woman", 2017),
    ("Frozen", 2013),
    ("Toy Story", 1995),
    ("Toy Story 3", 2010),
    ("Inside Out", 2015),
    ("Inside Out 2", 2024),
    ("Coco", 2017),
    ("Up", 2009),
    ("WALL-E", 2008),
    ("Finding Nemo", 2003),
    ("The Incredibles", 2004),
    ("Shrek", 2001),
    ("The Lion King", 1994),
    ("Wicked", 2024),
    ("The Super Mario Bros. Movie", 2023),
    ("Jurassic World", 2015),
    ("Furious 7", 2015),
    ("The Hunger Games", 2012),
    ("Twilight", 2008),
    ("Transformers", 2007),
    ("Pirates of the Caribbean: The Curse of the Black Pearl", 2003),
    ("The Godfather", 1972),
    ("The Godfather Part II", 1974),
    ("Goodfellas", 1990),
    ("Fight Club", 1999),
    ("The Shawshank Redemption", 1994),
    ("Schindler's List", 1993),
    ("Saving Private Ryan", 1998),
    ("Django Unchained", 2012),
    ("Inglourious Basterds", 2009),
    ("The Wolf of Wall Street", 2013),
    ("Arrival", 2016),
    ("Blade Runner 2049", 2017),
    ("Children of Men", 2006),
    ("District 9", 2009),
    ("Gravity", 2013),
    ("The Revenant", 2015),
    ("1917", 2019),
    ("Dunkirk", 2017),
    ("Tenet", 2020),
    ("The Prestige", 2006),
    ("Memento", 2000),
    ("Se7en", 1995),
    ("Zodiac", 2007),
    ("The Silence of the Lambs", 1991),
    ("No Time to Die", 2021),
    ("The Martian", 2015),
    ("Gravity", 2013),
    ("A Star Is Born", 2018),
    ("Bohemian Rhapsody", 2018),
    ("The Greatest Showman", 2017),
    ("Crazy Rich Asians", 2018),
    ("Hidden Figures", 2016),
    ("The Imitation Game", 2014),
    ("The Theory of Everything", 2014),
    ("Lincoln", 2012),
    ("Argo", 2012),
    ("The King's Speech", 2010),
    ("Slumdog Millionaire", 2008),
    ("Crash", 2004),
    ("Chicago", 2002),
    ("A Beautiful Mind", 2001),
    ("American Beauty", 1999),
    ("Shakespeare in Love", 1998),
    ("Titanic", 1997),
    ("Braveheart", 1995),
    ("Forrest Gump", 1994),
    ("Schindler's List", 1993),
    ("Unforgiven", 1992),
    ("The Silence of the Lambs", 1991),
    ("Dances with Wolves", 1990),
    ("Rain Man", 1988),
    ("Platoon", 1986),
    ("Amadeus", 1984),
    ("Terms of Endearment", 1983),
    ("Gandhi", 1982),
    ("Chariots of Fire", 1981),
    ("Ordinary People", 1980),
    ("Kramer vs. Kramer", 1979),
    ("The Deer Hunter", 1978),
    ("Annie Hall", 1977),
    ("Rocky", 1976),
    ("One Flew Over the Cuckoo's Nest", 1975),
    ("The Godfather Part II", 1974),
    ("The Sting", 1973),
    ("The Godfather", 1972),
    ("The French Connection", 1971),
    ("Patton", 1970),
    ("Midnight Cowboy", 1969),
    ("Oliver!", 1968),
    ("In the Heat of the Night", 1967),
    ("A Man for All Seasons", 1966),
    ("The Sound of Music", 1965),
    ("My Fair Lady", 1964),
    ("Lawrence of Arabia", 1962),
    ("West Side Story", 1961),
    ("The Apartment", 1960),
    ("Ben-Hur", 1959),
    ("Gigi", 1958),
    ("The Bridge on the River Kwai", 1957),
    ("Around the World in 80 Days", 1956),
    ("Marty", 1955),
    ("On the Waterfront", 1954),
    ("From Here to Eternity", 1953),
    ("The Greatest Show on Earth", 1952),
    ("An American in Paris", 1951),
    ("All About Eve", 1950),
]


def _dedupe(movies: list[tuple[str, int]]) -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    out: list[tuple[str, int]] = []
    for title, year in movies:
        key = (title.strip().lower(), year)
        if key in seen:
            continue
        seen.add(key)
        out.append((title, year))
    return out


def clamp_rating(value: float) -> int:
    return max(1, min(10, int(round(value))))


def build_rows(seed: int = 42) -> list[dict[str, str]]:
    rng = random.Random(seed)
    indie = _dedupe(INDIE)
    mainstream = _dedupe(MAINSTREAM)
    catalog = indie + mainstream
    indie_set = set(indie)
    mainstream_set = set(mainstream)

    named = [
        ("maya", "indie"),
        ("jordan", "horror"),
        ("sam", "blockbuster"),
        ("riley", "cinephile"),
    ]
    extras = [(f"user_{i:02d}", rng.choice(["indie", "horror", "blockbuster", "cinephile", "mixed"])) for i in range(1, 47)]
    people = named + extras

    horror_titles = {
        "The Witch",
        "Hereditary",
        "Midsommar",
        "The Lighthouse",
        "Get Out",
        "It Follows",
        "The Blair Witch Project",
        "The Texas Chain Saw Massacre",
        "Night of the Living Dead",
        "Longlegs",
        "The Substance",
        "I Saw the TV Glow",
        "Under the Skin",
    }

    rows: list[dict[str, str]] = []
    for username, taste in people:
        k = rng.randint(55, 95)
        chosen = rng.sample(catalog, k=min(k, len(catalog)))
        for title, year in chosen:
            is_indie = (title, year) in indie_set
            is_horror = title in horror_titles
            is_blockbuster = (title, year) in mainstream_set and not is_indie

            base = 6.0
            if taste == "indie":
                base = 8.4 if is_indie else 5.2
            elif taste == "horror":
                base = 8.6 if is_horror else (7.2 if is_indie else 5.5)
            elif taste == "blockbuster":
                base = 8.3 if is_blockbuster else 5.0
            elif taste == "cinephile":
                base = 8.0 if is_indie else 6.8
            else:
                base = 7.0 if is_indie else 6.5

            rating = clamp_rating(base + rng.gauss(0, 1.1))
            if rng.random() < 0.015:
                rating_field = ""
            else:
                rating_field = str(rating)
            rows.append(
                {
                    "Username": username,
                    "Movie Name": title,
                    "Year": str(year),
                    "Rating10": rating_field,
                    "Watched Date": f"2024-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
                    "Rating5": "",
                }
            )
    rng.shuffle(rows)
    return rows


def main() -> None:
    rows = build_rows()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Username", "Movie Name", "Year", "Rating10", "Watched Date", "Rating5"],
        )
        writer.writeheader()
        writer.writerows(rows)
    rated = sum(1 for row in rows if row["Rating10"])
    users = {row["Username"] for row in rows}
    titles = {(row["Movie Name"], row["Year"]) for row in rows}
    print(f"Wrote {OUT} ({len(rows)} rows, {rated} rated, {len(users)} users, {len(titles)} unique titles)")


if __name__ == "__main__":
    main()
