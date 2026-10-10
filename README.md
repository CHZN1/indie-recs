# Indie Recs

A Python API that recommends indie films from movie ratings. It trains a collaborative filtering model on all imported ratings, including mainstream films, then defaults to titles tagged for indie discovery. An optional expanded discovery mode adds untagged films with positive independent-production evidence.

The project uses FastAPI, SQLAlchemy, Surprise SVD, and TMDB metadata. It runs locally with SQLite by default; PostgreSQL is also supported.

## How it works

1. Upload a CSV containing usernames, movie titles, release years, and ratings.
2. Match each unique title and year against TMDB. If the year-specific result is missing or more than two years off, try a search without the year. Unmatched titles are skipped and reported in the response.
3. Store movie metadata and ratings, then train an SVD model on the full rating history.
4. Return up to 10 eligible films the requested user has not rated. Users without a trained profile receive a fallback ranked by rating count, average rating, and TMDB popularity.

TMDB responses are cached in SQLite or PostgreSQL and reused in memory during a run. Ratings stay on a 0–10 scale throughout training.

## What counts as indie?

A film is tagged as indie when its TMDB metadata matches at least one rule:

- A production company matches a whole name or phrase from the list in `app/indie.py`, such as A24, Annapurna, Neon, IFC, or Searchlight.
- A genre or keyword contains a phrase such as “independent film” or “indie film.”
- A keyword mentions a festival such as Sundance, SXSW, Tribeca, or Un Certain Regard.

These are broad rules, not a definitive classification. They include some studio specialty labels and can miss independently produced films when TMDB metadata is incomplete.

This is a discovery heuristic, not a verified record of financing or studio ownership. Festival appearances and specialty labels do not establish independent production. A missing tag means unknown under these rules. The demo offers **Indie discovery** (default) and **Expanded indie discovery**; integrations can request `/recommend/alice?scope=all`. Both modes exclude previously rated films and use the same trained model.

Both modes screen out Marvel/DC production or universe metadata, budgets of $40 million or more, and major-studio collections. Expanded discovery adds untagged films only when cached production-company metadata matches the independent-production list and does not match a major studio. Missing tags or a small budget alone do not qualify a film. The $40 million ceiling deliberately narrows discovery toward smaller productions, excluding films such as Arrival and Civil War even when independent companies are involved. Popularity alone is not an exclusion. Missing budgets remain unknown, so eligible films still need catalog review. These thresholds are product screening rules, not financial verification. The `scope=all` identifier is retained for compatibility; it now means expanded indie discovery. See [review data sources](docs/review-data-sources.md) for the real-data evaluation plan.

To inspect the reasons without changing the database or calling TMDB:

```bash
python scripts/audit_catalog.py --output /tmp/catalog-audit.json
```

The report stays outside the repository because it reflects the local catalog.

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

Development mode is an unauthenticated local demo. Authenticated backend mode supports provisioned bearer credentials, profile ownership checks, review storage, upload limits, and a separate training worker. Production configuration fails startup unless authentication and queued training are enabled. See [backend setup and remaining deployment requirements](docs/backend-deployment.md).

Movie matching uses title/year heuristics unless an explicit `TMDB ID` is supplied. Recommendations are limited to imported catalog films. Metadata lookup still runs during upload; production configuration queues model training for a separate worker. The container configuration is prepared, but has not been deployed or verified with Docker.

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

The local demo includes movie posters and a country selector for subscription,
rental, purchase, and free viewing options. Open “Where to watch” on a film to
check JustWatch availability through TMDB. A trained profile can receive
personalized recommendations with just one rating.

To compare history sizes against a fixed holdout, run:

```bash
python scripts/evaluate_history.py
```

See [frontend integration](docs/frontend-integration.md) for the experiment's
limits and the planned review-text comparison.

Review-text modeling is available as a local experiment, with ratings-only,
metadata, TF-IDF, and hybrid comparisons. It is not enabled in the API. See the
[review-text experiment](docs/review-text-experiment.md) for the first pilot,
reproduction steps, and limitations.

The [specific-preference research](docs/preference-research.md) adds a local
MovieLens ratings-and-tags comparison, 500 synthetic review diagnostics, and a
bounded feature adjustment for named composer and aesthetic preferences. This
remains experimental; the live API uses ratings-only recommendations.

The [separated review validation](docs/review-validation.md) selected a text blend on validation users, then tested fresh sparse profiles. Ratings alone performed better, so review reranking remains offline.

[Confirmed preferences](docs/confirmed-preferences.md) let viewers opt into a small composer or trait adjustment in the demo. Raw-review reranking remains offline. Prepared CSVs can include an optional `TMDB ID` to resolve same-title films directly.

## Current research and backend status

A review-text blend improved ranking on Amazon video products, but that benefit did not transfer clearly to a smaller movie-linked IMDb test. The indie-only chronological overlap had only four warm candidates and four test users, which is inadequate for a recommendation-quality claim. Automatic text reranking stays disabled. Human aspect-label tests on approximate English translations also showed substantial polarity errors. See [current roadmap results](docs/roadmap-results.md) for counts, methods, and the remaining data requirements.

Prepared CSVs can include a `Review` column. Reviews are stored against rated movies and can be read, updated, or deleted through owner-scoped endpoints. Storing a review does not change recommendations. Authenticated deployments require bearer credentials; the browser demo continues to run locally in development mode.
