# Indie Recs

A Python API that recommends indie films from movie ratings. It trains a collaborative filtering model on all imported ratings, including mainstream films, then filters recommendations to titles tagged as indie.

The project uses FastAPI, SQLAlchemy, Surprise SVD, and TMDB metadata. It runs locally with SQLite by default; PostgreSQL is also supported.

## How it works

1. Upload a CSV containing usernames, movie titles, release years, and ratings.
2. Match each unique title and year against TMDB. If the year-specific result is missing or more than two years off, try a search without the year. Unmatched titles are skipped and reported in the response.
3. Store movie metadata and ratings, then train an SVD model on the full rating history.
4. Return up to 10 indie films the requested user has not rated. Users without a trained profile receive a fallback ranked by rating count, average rating, and TMDB popularity.

TMDB responses are cached in SQLite or PostgreSQL and reused in memory during a run. Ratings stay on a 0–10 scale throughout training.

## What counts as indie?

A film is tagged as indie when its TMDB metadata matches at least one rule:

- A production company contains a name from the list in `app/indie.py`, such as A24, Annapurna, Neon, IFC, or Searchlight.
- A genre or keyword contains a phrase such as “independent film” or “indie film.”
- A keyword mentions a festival such as Sundance, SXSW, Tribeca, or Un Certain Regard.

These are broad rules, not a definitive classification. They include some studio specialty labels and can miss independently produced films when TMDB metadata is incomplete.

## Setup

Use Python 3.10 or later and a TMDB v3 API key from your [TMDB account settings](https://www.themoviedb.org/settings/api).

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Set `TMDB_API_KEY` in `.env`. Keep this file private; it is excluded from Git, Docker builds, and the upload ZIP. If `.env` already exists, edit it instead of copying over it.

Surprise compiles native code. If installation fails because a compiler is missing, install Xcode Command Line Tools on macOS or `build-essential` on Debian/Ubuntu and retry.

The default database is `data/indie_recs.db`. To use PostgreSQL, set `DATABASE_URL` in `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/indie_recs
```

Other settings, including the model path and metadata cache lifetime, are listed in `.env.example`.

## Visual demo

With the API running, open [localhost:8000/demo](http://127.0.0.1:8000/demo). The page lets you switch sample profiles, import a CSV, and see real recommendations with predicted ratings. You can also expand the request log to inspect the API responses.

The demo uses the configured database and model. On a fresh installation, import a sample CSV first; the four profile shortcuts use the larger synthetic sample. The small sample button imports Alice, Bob, and Carol.

See [frontend integration](docs/frontend-integration.md) for request examples and what a separate frontend needs.

## CSV format

The importer expects a prepared CSV with these columns:

- `Username`: the profile identifier used by `/recommend/{user_id}`.
- `Movie Name`: the movie title.
- `Year`: release year; blank or invalid values fall back to a title-only search.
- `Rating10`: a numeric rating from 0 to 10. Blank, nonnumeric, or out-of-range ratings are skipped.

This is a Letterboxd-style input format, not a direct integration with Letterboxd. Prepare your export to match these columns before uploading. If your source uses 0–5 ratings, multiply them by two to populate `Rating10`. Extra columns, including `Watched Date` and `Rating5`, are ignored.

The sample files contain fictional users and ratings:

- `sample_data/letterboxd_ratings.csv`: a small example for trying the API.
- `sample_data/letterboxd_large.csv`: generated ratings for 50 fictional users.

Uploading an existing user/movie pair replaces its stored rating.

## Run the API

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the interactive API docs at [localhost:8000/docs](http://127.0.0.1:8000/docs).

```bash
curl -F "file=@sample_data/letterboxd_ratings.csv" http://127.0.0.1:8000/upload
curl http://127.0.0.1:8000/recommend/alice
curl http://127.0.0.1:8000/stats
curl http://127.0.0.1:8000/health
```

`POST /upload` imports ratings and saves a retrained model to `models/svd_model.joblib`. Its response includes import counts and warnings. Recommendations report `strategy: "cf"` when the model is used and `strategy: "cold_start"` for the fallback.

## Tests and evaluation

Run the unit tests without calling TMDB:

```bash
pytest
```

For an import and model evaluation using the larger sample:

```bash
python scripts/generate_large_export.py
python scripts/run_large_test.py --fresh
```

**`--fresh` deletes all project tables in the configured database and removes the saved model.** Use a disposable database for this run. Stop the API first and restart it afterward.

The script calls TMDB, trains the model, reports RMSE and MAE on a 20% holdout, and prints recommendations for four sample users. The ratings are synthetic, so these scores help check the pipeline; they do not establish recommendation quality for real users. Runtime depends on network speed and the metadata cache.

## Maintenance

```bash
python scripts/retrain.py
python scripts/tag_indie.py
```

Retrain after changing stored ratings outside the upload endpoint. Run `tag_indie.py` after editing the classification rules. It applies the current rules to cached movie metadata, fetching from TMDB when a cache entry is missing or expired.

## Docker

```bash
docker build -t indie-recs .
docker run --env-file .env -p 127.0.0.1:8000:8000 indie-recs
```

Database and model files stay inside the container unless you mount persistent storage. Removing the container removes those files.

## Current limitations

This is a local demo. It has no login or access controls: anyone who can reach the API can upload ratings for any username or request that profile's recommendations. Keep it local until authentication and deployment controls are added.

Movie matching uses title, year, and popularity, so ambiguous titles can resolve incorrectly. Recommendations are limited to films already imported into the database. Uploads perform metadata lookups and training during the request, which can take time for larger files.

Only load model files you created yourself; joblib uses pickle-based serialization.

## Project layout

```text
app/           API, database models, importer, TMDB client, and recommendation logic
scripts/       Sample generation, evaluation, retraining, retagging, and ZIP packaging
sample_data/   Fictional ratings in the expected CSV format
tests/         Unit tests
demo/          Browser demo served by the API
docs/          Frontend integration notes
data/          Local database (excluded from Git)
models/        Trained model (excluded from Git)
```

To build the GitHub upload ZIP:

```bash
python scripts/pack_github_zip.py
```

The archive is written to `dist/indie-recs-github.zip`. Extract it and upload the contents of the `indie-recs` folder so `README.md` sits at the repository root. Include the hidden `.gitignore`, `.dockerignore`, and `.env.example` files.

## License

MIT; see `LICENSE`. Movie metadata comes from TMDB. Review the [TMDB terms](https://www.themoviedb.org/documentation/api/terms-of-use) before using its metadata or images in a public app.
