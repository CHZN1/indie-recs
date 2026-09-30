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

Each recommendation includes an internal movie ID, TMDB ID, title, year, indie flag, overview, poster path, popularity, and a nullable rating estimate. With `strategy: "cf"`, the rating is the model's prediction on a 0–10 scale. With `strategy: "cold_start"`, it is the average local rating, or null if no ratings exist.

`GET /stats` returns profile, movie, indie-movie, and rating counts. `GET /health` reports basic availability. The full response schemas are available at `/docs` and `/openapi.json`.

## Hosting a separate frontend

The bundled demo shares the API's origin, so it needs no CORS configuration. A frontend hosted elsewhere needs either a same-origin reverse proxy to this API or explicitly configured CORS for that frontend's origin. CORS middleware is not enabled by default. Backend-to-backend HTTP calls do not require browser CORS.

The TMDB key stays in backend configuration. A frontend sends ratings and profile identifiers; it never needs the TMDB key.

## Before using this in a production product

The demo demonstrates the HTTP integration, not production readiness. The API currently trusts supplied usernames and has no authentication, ownership checks, or tenant isolation. A commercial integration needs authenticated identities and authorization, request and upload limits, controlled deployment, and a data privacy policy appropriate to the product.

Imports perform metadata requests and model training during the upload request. For larger workloads, move that work to background jobs with progress reporting. Database writes and model replacement also need concurrency control before accepting simultaneous uploads. Add deployment monitoring and test the system against real rating data before claiming recommendation quality.

Movie matching and indie tagging are heuristic. The catalog includes only imported movies. The code is MIT licensed, which permits commercial reuse with its license and copyright notice retained. Review dependency licenses for the intended distribution. TMDB provides a free developer API for attributed, noncommercial use; contact TMDB about a commercial license before using its API in a commercial product. See the [TMDB FAQ](https://developer.themoviedb.org/docs/faq).
