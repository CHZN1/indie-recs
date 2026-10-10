# Roadmap results — 2026-10-09

## 1. Movie-linked review histories: prepared

Downloaded the author-published [IMDb Spoiler Dataset](https://www.kaggle.com/datasets/rmisra/imdb-spoiler-dataset), described in [Misra's paper](https://arxiv.org/abs/2212.06034). The archive contains 573,913 reviews with user IDs, IMDb movie IDs, dates, text, and ratings. `scripts/prepare_imdb_histories.py` joins exact IMDb identifiers already present in cached TMDB movie details, then checks release years within one year. One year conflict was excluded. No fuzzy title matching or IMDb scraping was used.

The resulting overlap contains 100,549 reviews from 67,124 users across 152 catalog movies. Fourteen match current strict discovery eligibility, and 21 match expanded eligibility. Review text and user identifiers remain outside the repository. Exact cached IDs reduce ambiguity but are not an independent manual verification of all catalog records. These research data must not be assumed cleared for commercial use.

## 2. Movie-specific ranking comparison: evaluated; promotion failed

The chronological training split contains 60,325 interactions and 109 warm movies. The broader movie diagnostic uses 259 validation users and 74 different test users. Validation selected item similarity plus ten percent review text, but test NDCG@10 fell from 0.15828 for ratings alone to 0.15346 for the blend. The paired difference interval [-0.03375, 0.02547] includes both benefit and harm. Top-ten hit rate fell from 32.43 to 29.73 percent. These are small observational samples, not a definitive rejection of all text models.

The strict indie-only run contains just four warm eligible candidates, five validation users, and four test users. Its perfect top-ten recall is an artifact of ranking fewer than ten candidates. It does not validate indie recommendations or single-rating performance. Its validation selection chose zero text. More historical indie coverage and returning reviewers are required before promotion.

Both tests used the same fixed baseline/blend grid as the previous Amazon validation, with all fitting on earlier reviews and ratings. The `catalog` scope exists only in the offline evaluator; the API still supports strict and expanded indie discovery with mainstream exclusions. No product filtering was relaxed to improve test numbers.

## 3. Independent aspect labels: benchmark complete; automatic inference pending

Downloaded [MABSA v4](https://data.mendeley.com/datasets/f3ftpd7xpg/4), by Syam Mohan E and R Sunitha, DOI 10.17632/f3ftpd7xpg.4, published under CC BY 4.0. It provides human aspect annotations of Malayalam movie reviews and approximate English translations. The translation file's SHA-256 was checked against the publisher inventory. No raw reviews are redistributed here.

`scripts/evaluate_mabsa_aspects.py` groups duplicates linked by either original or translated text. It trains on 2,394 reviews, selects regularization on 799 validation reviews, and evaluates once on 807 held-out reviews. Missing aspect labels are treated as absent, separately from explicitly neutral opinions. Nine independent TF-IDF logistic-regression classifiers predict absent, negative, neutral, or positive.

On explicitly mentioned aspects, exact polarity accuracy is 73.30 percent for Camera, 57.61 percent for BGM, and 65.87 percent for Songs. Four-class macro F1 is 0.7584, 0.7722, and 0.6579 respectively. These metrics answer different questions; a high four-class score does not imply reliable polarity on mentioned aspects. Reviewer/movie separation cannot be checked because those identifiers are unavailable. Approximate translations are not native English reviews. No labels establish preferences for named composers, musical similarity, lighting styles, or a Wes Anderson aesthetic. POM access is still pending registration and license acceptance.

## 4. Catalog eligibility: automated audit complete

The cached catalog contains 314 movies and 53 stored discovery tags. Hard exclusions leave 51 strict and 70 expanded candidates. Fourteen eligible films have unknown budgets. No eligible film has only festival-keyword evidence. Two low-vote titles are flagged for identity review; that signal does not prove a wrong match. All cached tags recompute consistently, but that is consistency with the heuristic, not proof of financing independence.

Retain the under-$40-million screening policy and positive production evidence for expanded discovery. Popularity is not an exclusion: an inexpensive independent film can become well known. Missing budgets remain unknown and stay visible in the audit. Marvel/DC, major-studio collections, and known budgets of $40 million or more remain excluded. Factual financing/ownership classification and inflation-adjusted budget policy are not complete.

## 5. Review integration: storage complete; automatic scoring held back

Owner-scoped PUT/GET/DELETE review endpoints attach text to an already rated film using its TMDB ID. Prepared CSVs optionally upsert a nonblank `Review` column. Blank CSV values preserve existing reviews. Text is capped at 20,000 characters and is never returned to another ordinary credential. The recommendation model does not consume stored text yet, because the movie-specific promotion gate failed. Explicitly confirmed preferences remain available.

## 6. Backend deployment preparation: implemented and locally tested

Provisioned bearer credentials, revocation, profile ownership, upload size limits, persistent training jobs, a separate serialized worker, and atomic model publication are implemented. Production configuration requires authentication and background training. This is service-credential authentication, not consumer login or tenant isolation. Reviews remain private database data. Tokens are hashed in the database and provisioned only to private files outside the project.

`compose.yaml` prepares non-root API and worker containers with persistent storage and a loopback listener. Docker was unavailable on this machine, so the container build and deployment are unverified. No public service was deployed. HTTPS ingress, rate limits, operational monitoring/backups, distributed concurrency, account flows, and appropriate data/API rights remain deployment requirements. See [backend setup](backend-deployment.md).

## 7. Publication

The upload package excludes private exports, research inputs, database files, trained models, credentials, logs, temporary files, and lock files. Aggregate research results and reproducible scripts are public-project material. GitHub synchronization is recorded separately from local completion; prepared code is not a deployed service. Portfolio wording should say that review text improved the Amazon product benchmark but did not yet demonstrate an indie-movie improvement.

## Remaining priority

Collect or license movie-linked indie review histories with repeat reviewers and useful historical coverage. Run a new untouched movie-level evaluation before enabling automatic text scoring. Do not keep tuning on the reported tests or treat those tests as proof that no other method can help.
