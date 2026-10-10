# Review-text experiment

The review-text model is an experimental local tool. The recommendation API
continues to use ratings-only SVD. The first pilot did not establish a benefit
from review text, so it has not been enabled in the demo or API.

## What it compares

The experiment runs the same held-out films and candidate movies through:

- Ratings-only SVD, using the production training settings.
- A rating-weighted metadata profile, without user review words.
- A rating-weighted TF-IDF review profile matched against movie metadata.
- Hybrids with predetermined text weights of 25%, 50%, and 75%.

The metadata control helps distinguish review wording from content matching.
Metadata consists of cached plot summaries, genres, and keywords. Titles are
excluded from the text documents. There is no new network request, and no review
is sent to TMDB or another service.

TF-IDF uses words and pairs of words, sublinear term frequency, and normalized
vectors. Vocabulary and IDF are fit on public catalog metadata only. Reviews are
transformed using that vocabulary; unknown words do not produce matches. A
review's weight is `(rating - 5) / 5` on the 0–10 rating scale, so a low rating
reduces the score of matching content. The user vector is normalized before
cosine scoring. This is a heuristic preference weight, not a sentiment model.

Hybrid scoring blends percentile ranks rather than mixing rating predictions
with cosine scores on incompatible scales. Equal scores receive average ranks.
If the reviews have no usable signal, the hybrid preserves ratings-only ordering.
A single rated review can form a profile; the evaluation needs at least two
reviewed films to hold one out.

## How to run it

Import the viewer's ratings locally first. Then use the native Letterboxd
`reviews.csv`, with its `Name`, `Year`, and `Review` columns:

```bash
python scripts/evaluate_reviews.py \
  --reviews /path/to/private-letterboxd-export/reviews.csv \
  --user your-local-username \
  --output /path/outside-this-repository/review-results.json
```

Those paths are placeholders. The script refuses to write the report inside the
repository, so personal rankings and matched terms cannot enter the upload ZIP
through this command. Keep the original export outside the repository as well.
The experiment does not overwrite the database or saved production model.

Reviews resolve through the importer's cached title/year match or a unique exact
catalog title/year match. Unmatched reviews produce warnings. Multiple reviews
for the same resolved film are rejected rather than silently picking a rewatch.
Ratings come from the local database, which must contain that viewer's ratings.

## Evaluation and first pilot

Leave one reviewed film out at a time. Remove its rating from SVD training and
its review from the viewer's text profile. All other users' ratings stay fixed.
Exclude the viewer's remaining rated films from the candidates. The target film
is returned to the candidate pool for evaluation. Public target-film metadata
remains available, as it would for a new movie at recommendation time.

Report mean rank, hit rate at ten, mean reciprocal rank, and NDCG at ten. With one
held-out relevant film per fold, NDCG is its logarithmic rank discount. For tied
scores, metrics are expected values over random tie ordering, preventing movie
IDs from giving a method an accidental advantage. Other unrated candidates are
unknown preferences, not confirmed dislikes. This is a retrospective retrieval
test, not a temporal prediction test.

The first run used five highly rated reviews from one real viewer and synthetic
ratings from the other viewers, against a catalog of 314 movies. Each fold had
310 candidates. Mean ranks were 148.2 for SVD, 141.2 for the metadata control,
168.2 for review text, and 150.9, 161.1, and 164.7 for the three hybrid weights.
All methods had zero top-ten hits across the five full-catalog folds. These
results do not support enabling review text as a general quality improvement.

Only two held-out movies had other-user ratings. The other three were new items
for SVD, which cannot learn their item factors. Only one held-out movie passed
the current indie metadata rules, so the indie-only comparison has one fold and
cannot support an indie ranking-quality claim. In that single fold, ratings-only
ranked the target tenth and the 25% text hybrid ranked it eleventh. The report
separately includes full-catalog, known-item, and indie-only results.

Approximately 31–36% of the review's analyzed words and word pairs appeared in
the metadata vocabulary. That is lexical coverage, not semantic understanding.
Full-history top-ten lists and matching terms are included for inspection only;
changing that list is not evidence of better recommendations.

## What to test next

Collect more real viewers, varied ratings, and reviews with specific preferences.
Use a separate validation set to choose hybrid weights, then evaluate an untouched
test set. Evaluate short and long histories separately and retain known-item and
new-item breakdowns. Gather feedback on recommendations the viewer has not seen.

Plot summaries often omit lighting, soundtrack style, and composers. Add reliable
movie-side features before expecting those review words to match. Simple word
matching can confuse “got high” with “high school,” and it does not understand
that “not action packed” differs from liking action. Preserving negation words
and using word pairs does not resolve sentiment scope or synonyms. Those are
reasons to test better features and language representations, not to assume a
more complex model will improve results.

The tests cover held-out rating/review exclusion, one-review scoring, specific
lighting/music terms in controlled fixtures, negative rating weights, unknown
words, HTML cleanup, ties, and no-signal fallback. The controlled fixtures test
mechanics; they are not synthetic evidence of real recommendation quality.

Implementation: `app/review_text.py` and `scripts/evaluate_reviews.py`.
TF-IDF behavior follows the
[scikit-learn text feature documentation](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction).

## Creative-credit metadata comparison

The next metadata variant adds factual composer, cinematographer, director, and
editor names from [TMDB credits](https://developer.themoviedb.org/reference/movie-credits).
Roles are matched exactly: a music supervisor is not recorded as the original
score composer, and a lighting technician is not recorded as the cinematographer.
Missing credits remain missing. Names and job labels do not establish musical
style, lighting quality, or mood.

Fetch credits for the catalog once, using the same server-side TMDB key:

```bash
python scripts/enrich_creative_credits.py
```

This sends movie IDs to TMDB, never reviews or usernames. Responses are cached
locally with the existing metadata TTL. The script reports role coverage and
failed requests; rerunning reuses unexpired credits. It changes only cached public
metadata, not ratings or the saved SVD model.

Rerun the review experiment with `--creative-credits` and a separate private
output file. Omitting the flag reproduces the original feature set. The expanded
variant requires a cached credits response for every catalog movie; it will not
silently compare a partially enriched catalog. Empty role lists are valid missing
credits, distinct from a movie whose credits were never fetched.

Keep the original holdout, SVD parameters, and hybrid weights fixed when comparing
these feature sets. Report lexical coverage alongside ranking metrics. Better
coverage alone does not establish better recommendations. Reviews must actually
name composers or cinematographers for person-name matching to be informative.

The completed enrichment fetched all 314 catalog movies without request failures.
Original-score composers were listed for 280 movies, cinematographers for 305,
directors for 314, and editors for 310. These counts describe this local catalog,
not TMDB's overall coverage.

For the controlled comparison, use `--full-vocabulary` on **both** the original
and expanded runs. The original 20,000-term cap can discard existing words when
credits are added. Removing the cap yielded 20,023 terms in the original corpus
and 23,983 in the expanded corpus. The report records the cap and vocabulary size.

With the full vocabulary, review-only mean held-out rank improved from 168.2 to
160.6; the 25% hybrid changed from 150.9 to 148.3. Ratings-only remained 148.2.
Every method still had zero top-ten hits in the five full-catalog folds. Review
lexical coverage remained unchanged at approximately 31–36%. The five reviews
do not name the credited creators, so these shifts do not demonstrate composer
preference learning. The single indie-only fold also continued to favor SVD.
The added features are available for further testing, but the API remains
ratings-only.
