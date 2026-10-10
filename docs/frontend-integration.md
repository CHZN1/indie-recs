# Frontend integration

The recommendation engine exposes HTTP endpoints. A frontend can call them without importing the Python recommendation code.

## Try the working demo

Start the API from the project root:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/demo. The page uses real requests to `/health`, `/stats`, `/upload`, and `/recommend/{user_id}`. It shows stored movie metadata and model results, not hardcoded recommendations. The sample import updates the configured database and retrains its saved model.

The four profile shortcuts correspond to the larger synthetic sample. Import `sample_data/letterboxd_large.csv` to populate them on a fresh installation. The small sample button creates Alice, Bob, and Carol instead. A new installation has no movies or trained model until ratings are imported.

## Request examples

Upload prepared ratings using multipart form data. Let the browser set the multipart Content-Type boundary:

```javascript
const form = new FormData();
form.append('file', csvFile);
const response = await fetch('/upload', { method: 'POST', body: form });
const result = await response.json();
if (!response.ok) throw new Error(result.detail);
```

Get recommendations using the profile identifier:

```javascript
const response = await fetch(`/recommend/${encodeURIComponent(userId)}`);
const result = await response.json();
if (!response.ok) throw new Error(result.detail);
// result.user_id, result.strategy, result.recommendations
```

`GET /recommend/{user_id}?scope=indie` is the default; `scope=all` adds independently supported production candidates, with mainstream exclusions. Unknown scope values return HTTP 422. The demo exposes the same choice. This changes eligibility, not the model or its rating estimates.

Each recommendation includes an internal movie ID, TMDB ID, title, year, indie flag, overview, poster path, popularity, and a nullable rating estimate. With `strategy: "cf"`, the rating is the model's prediction on a 0–10 scale. With `strategy: "cold_start"`, it is the average local rating, or null if no ratings exist.

`GET /stats` returns profile, movie, indie-movie, and rating counts. `GET /health` reports basic availability. The full response schemas are available at `/docs` and `/openapi.json`.

## Hosting a separate frontend

The bundled demo shares the API's origin, so it needs no CORS configuration. A frontend hosted elsewhere needs either a same-origin reverse proxy to this API or explicitly configured CORS for that frontend's origin. CORS middleware is not enabled by default. Backend-to-backend HTTP calls do not require browser CORS.

The TMDB key stays in backend configuration. A frontend sends ratings and profile identifiers; it never needs the TMDB key.

## Before using this in a production product

The demo demonstrates the HTTP integration, not production readiness. Development mode trusts supplied usernames. Authenticated mode checks provisioned bearer credentials and profile ownership, limits uploads, and disables the browser demo. See [backend deployment](backend-deployment.md) for the integration contract and remaining hosting, privacy, and operational work.

Metadata lookup remains synchronous. With background training enabled, uploads return a training job ID and a separate worker publishes the model atomically. A shared-directory worker lock serializes training, but concurrent imports and distributed workers need additional operational design. Add deployment monitoring and test the system against real rating data before claiming recommendation quality.

Movie matching and indie tagging are heuristic. The catalog includes only imported movies. The code is MIT licensed, which permits commercial reuse with its license and copyright notice retained. Review dependency licenses for the intended distribution. TMDB provides a free developer API for attributed, noncommercial use; contact TMDB about a commercial license before using its API in a commercial product. See the [TMDB FAQ](https://developer.themoviedb.org/docs/faq).

## Posters and watch availability

The demo displays each film's poster, title, release year, and TMDB detail link.
Missing or failed poster images do not prevent recommendations from loading.

`GET /movies/{tmdb_id}/watch-providers?region=US` returns availability for a movie
in the local catalog. Use an uppercase two-letter country code. Results separate
subscriptions (`flatrate`), rentals (`rent`), purchases (`buy`), free services
(`free`), and services with ads (`ads`). An empty listing means no offers are
listed for that country; it is not proof that the film cannot be watched.

The demo fetches availability when the viewer opens a film's “Where to watch”
section. Changing country closes the sections so the next check uses that country.
Provider responses are cached for 24 hours. Failed requests remain retryable and
are displayed separately from empty results. The API key stays on the server.

Availability comes from JustWatch through TMDB, with attribution in the demo.
The returned TMDB watch-page URL provides links to offers; the API does not supply
direct provider links or current prices. See the
[TMDB watch-provider documentation](https://developer.themoviedb.org/reference/movie-watch-providers).

## Rating-history comparison

Run `python scripts/evaluate_history.py` against a populated local database.
The experiment selects up to twelve users with at least sixty ratings. Each user
has ten fixed held-out ratings, and nested histories of 1, 5, 10, 25, and 50 ratings.
Other users' ratings stay unchanged. No held-out rating enters the target user's
training history. Models use the same SVD parameters and random seed.

The initial synthetic-data run measured RMSEs of 1.5990, 1.5688, 1.5392, 1.3955,
and 1.2421 respectively, on the 0–10 scale. The item-mean baseline was 1.6075.
Each condition evaluated the same 120 held-out ratings. This is one seeded
experiment with synthetic preferences, not a real-world accuracy claim or a
ranking-quality benchmark. Larger histories reduced prediction error in this run.
One rating still qualifies a trained user for personalized recommendations.

## Review-text experiment

Review text is not used by the current API model. A local TF-IDF and hybrid
pilot is implemented in [the review-text experiment](review-text-experiment.md).
Its first results did not justify changing the API. That document covers the
held-out comparison, metadata control, lexical coverage, and next experiments.

## Confirmed preferences

The optional [confirmed-preference contract](confirmed-preferences.md) provides catalog options and a stateless POST recommendation endpoint with bounded adjustments and explanations. The standard GET remains ratings-only. Authenticated mode enforces profile ownership on both recommendation routes. Manual preferences remain stateless.

Prepared uploads may include a `TMDB ID` column. Positive IDs bypass title matching; blanks retain heuristic matching. This is useful for same-title films and festival/release-year differences.

## Stored reviews and queued training

Authenticated clients send an owner credential in the Authorization bearer header. `PUT /users/{user_id}/reviews/{tmdb_id}` stores text for an already rated catalog film; GET reads it and DELETE removes it. Reviews are not automatically used for ranking. CSV imports optionally accept `Review` alongside an explicit `TMDB ID`.

Uploads in queued mode return `training_job_id` and `model_retrained: false`. Poll `GET /training/jobs/{id}` for queued/running/succeeded/failed status. Continue using the previous model while training runs. Authentication and limits are described in [backend deployment](backend-deployment.md).
