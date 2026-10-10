# Authenticated backend preparation

The browser demo remains a local development tool. Authenticated mode disables `/demo` and `/demo/sample`; this change does not add a login frontend. Automatic review-text recommendation scoring remains disabled because movie-specific validation did not establish an improvement.

## Credentials and ownership

Set `ENVIRONMENT=production`, `AUTH_REQUIRED=true`, and `BACKGROUND_TRAINING=true`. Configuration rejects production startup if either protection is missing. Development defaults retain the existing unauthenticated local demo; do not expose that mode publicly.

Provision integration credentials with:

```bash
python scripts/manage_credentials.py issue --user viewer --output /private/tmp/indie-viewer.token
```

Use a private file outside the project. The CLI creates a new file with mode 0600 and never prints its token. It can create a profile or attach a credential to an existing profile. Tokens contain 256 bits of randomness; only a SHA-256 digest is stored in the database. This is suitable for random service credentials, not password hashing. Send the token in `Authorization: Bearer <token>` over HTTPS. Tokens have no automatic expiry in this version; revoke and replace them on a defined schedule or when compromised:

```bash
python scripts/manage_credentials.py revoke --credential-id 1
```

An ordinary credential can recommend for, refine, upload ratings for, and read/write/delete reviews for its own profile. A CSV containing another username is rejected before metadata lookup or mutation. Administrator credentials (`issue --admin`) deliberately have cross-profile access and can queue global training. Provision them only to backend operators. There is no public account creation, password login, OAuth, recovery, or browser token storage. An acquiring company's backend can authenticate its own users and hold these credentials server-side; do not embed administrator tokens in a frontend bundle.

`/health` and API schema documentation remain public. Profile recommendation endpoints, preferences, catalog statistics, watch-provider requests, reviews, and training job endpoints require a valid credential in authenticated mode. Revocation is checked on every request. Tokens and review contents are not logged by these handlers; HTTP client request logging is suppressed to avoid logging the TMDB key query parameter.

## Review data

`PUT /users/{user_id}/reviews/{tmdb_id}` accepts `{"text":"..."}` for an already rated catalog film. Read or delete it with GET/DELETE at the same path. Text is limited to 20,000 characters. Owner checks run before profile lookups. Responses explicitly state `used_for_ranking: false`.

Prepared ratings CSVs may include `Review` and `TMDB ID` columns. Nonblank review text is upserted with the successfully imported rating. Blank values leave existing text alone; DELETE explicitly removes it. Overlong review text fails preflight before imports. Research reviews are not automatically imported into personal profiles. Database backups contain private review text and must have restricted access and retention policies.

## Training lifecycle

With background training enabled, `/upload` returns `model_retrained: false` and `training_job_id`. The import and metadata resolution still happen within the request; only model training is queued. Poll `GET /training/jobs/{id}` with the owner or administrator credential. Administrators can POST `/training/jobs` without another import.

Run one worker per shared model directory:

```bash
python scripts/training_worker.py --poll-seconds 2
```

The queue persists in the database. A filesystem lock serializes workers sharing that directory. Jobs transition queued → running → succeeded/failed. Model artifacts are published using a temporary file and atomic rename, so readers retain a complete previous model while training runs. Failed jobs retain the prior model. A worker killed during training can leave a running job; inspect it and queue a replacement. There is no automatic lease/retry system. This worker targets Linux/macOS and a shared filesystem, not distributed replicas. Do not load third-party joblib artifacts.

## Container configuration

`compose.yaml` prepares an API and separate worker, with persistent database and model volumes. Both run as a non-root user. The API binds to loopback port 8080. A real server needs an HTTPS reverse proxy, request/body rate limits, restricted volume backups, monitoring, and an appropriate TMDB commercial agreement where applicable. The application limits ratings CSV reads to 5 MB by default; ingress limits must also bound multipart requests.

```bash
docker compose up --build -d
# Provision within the container; save/copy the private token securely before replacing it.
docker compose exec api python scripts/manage_credentials.py issue --user operator --admin --output /tmp/indie-operator.token
```

Local unit/integration tests exercise ownership, token rejection/revocation, upload preflight, review lifecycle, queue success/failure, and atomic publication. Container deployment requires Docker and has not been executed merely by writing this configuration. No hosting account or public service has been created. SQLite and a single API/worker deployment are the documented starting point; distributed training and production database migration tooling remain future work.
