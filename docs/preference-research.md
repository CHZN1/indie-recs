# Testing specific review preferences

This is an offline research extension. The live API continues to use ratings-only
SVD. We now have separate experiments for real ratings and tags, constructed
review language, and a bounded adjustment to ratings-model scores.

## Sources and what they can tell us

[MovieLens latest-small](https://grouplens.org/datasets/movielens/latest/) supplies
100,836 real ratings and 3,683 free-text tag applications from 610 anonymized
users. Its TMDB IDs let us match 196 local catalog movies without guessing titles.
The matching subset has 12,983 ratings. Six users have at least five movies with
both a tag and a rating. These tags are short descriptions, not full reviews or
reliable statements of what the user liked.

The local comparison holds out five randomly selected liked films per eligible
user (rating at least 8/10), removing that film's rating and all of that user's
associated tags. The remaining rated tags form the user's text profile. Other
users' MovieLens ratings stay fixed. This experiment never includes the fictional
sample users or the owner's Letterboxd ratings. Results average each user's fold
means so every evaluated user has equal weight. Metadata features and full
vocabulary settings are fixed across methods.

The experiment uses the existing 314-film catalog, including candidates without
MovieLens ratings. It is a retrospective local catalog test, not the standard
MovieLens benchmark. The source ZIP's SHA-256 is recorded in the report.

On 30 held-out liked films, ratings-only recovered four in the top ten; 25% and
50% TF-IDF hybrids recovered five and six respectively. Ratings-only had higher
MRR (0.11794) and NDCG at ten (0.10964) than the 50% hybrid (0.06066 and 0.08693).
The tradeoff is mixed, and six selected users are too few to establish a winner.
The new structured adjustment found no explicit supported preference statements
in the tag profiles, so it preserved ratings-only results. That is abstention,
not evidence that structured preferences improve real-world recommendations.

MovieLens is used locally under its research terms. It is not product training
data or part of the GitHub ZIP. Its license requires separate permission for
commercial or revenue-bearing use. Keep the original dataset license intact.
Citation: F. Maxwell Harper and Joseph A. Konstan. 2015. *The MovieLens Datasets:
History and Context*. ACM TiiS 5(4), 19:1–19:19. DOI:10.1145/2827872.
See the [publisher's terms](https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html).

[Cornell's movie-review collections](https://www.cs.cornell.edu/people/pabo/movie-review-data/)
are another source for sentiment experiments. They are not a ready-made drop-in
user/movie/TMDB recommendation dataset; a sentiment label alone does not tell us
which visual or musical aspect a reviewer liked. No new website scraping was
needed for this stage.

## Feature definitions

Creative credits provide factual composer, director, and cinematographer names.
`research/curated_features.json` adds a small manual feature map with supporting
sources. An absent annotation means unknown, not that the movie lacks a style.

- Wes Anderson aesthetic references map to a small set of visual traits: framing
  symmetry, pastel palettes, and whimsical production design. These annotations
  are editorial, not an automatic definition for all of his films.
- Paddington 2 shares the curated pastel/whimsical traits, supported by a BFI
  review drawing that comparison. This allows a cross-director match rather than
  treating a shared surname as a visual similarity.
- Birdman's original score is largely Antonio Sánchez's jazz percussion, with
  classical music also present. A generic Birdman score reference maps to jazz
  percussion and Sánchez; it does not imply Hans Zimmer.
- Whiplash supplies a jazz-percussion connection through on-screen performance.
  This is a broad musical association, not a claim that its score is identical
  to Birdman's or that the films share a composer.

Person-name matching supports explicit aliases for “Hanz Zimmer” and “Wes
Andersson,” plus accent normalization. It does not guess that composers with
different names have similar music. More detailed musical similarity needs
additional reliable instrumentation, texture, and score-style annotations.

Birdman and Paddington 2 are documented reference candidates in controlled tests;
they were not added to the live database. The live indie rule currently excludes
all fifteen catalog films credited to Hans Zimmer and excludes several other
example films. This is a candidate-filter constraint, independent of whether a
review preference can be recognized. Test full-catalog matching separately and
retain the product's indie filter when checking production eligibility.

## Ratings-first adjustment

`app/review_features.py` extracts supported named features only when a clause has
an explicit positive or negative sentiment cue. Factual credits alone do not
establish a preference. Clauses split at punctuation and contrast words such as
“but.” Low ratings can coexist with a positive comment about the music, while a
high overall rating can coexist with disliking that music.

The numeric rating controls evidence strength. Ratings-model predictions remain
the base score. Matching content can adjust that score by at most 0.2 points for
one film, then 0.1 more per consistently supporting distinct reviewed film,
up to 0.7 points on the 0–10 scale. Negative preferences can subtract points.
These are conservative heuristic limits, not parameters selected by validation.
Adjusted scores are ranking scores, not calibrated rating predictions.

Repeated words, repeated clauses, and duplicate reviews of the same film do not
increase the distinct-film count. Opposing opinions reduce support; balanced
opposing evidence produces no adjustment. Missing supported preference evidence
leaves ratings-only scores unchanged. A single clue cannot overturn a large
ratings-model gap. Many small rating-score gaps can still change the order, so
this is not a guarantee that all rankings remain mostly unchanged.

## Synthetic language diagnostics

The generator creates 100 fictional profiles, each with five original snippets:
500 reviews spanning terse, conversational, detailed, mixed low-rating, negative,
factual, sarcastic, and implicit wording. Ratings span 1–10, with low overall
ratings deliberately paired with positive aspect opinions in the mixed cases.
Profiles mention music, style, or a composer on between one and five distinct
films. Typos appear in a subset. These are templated diagnostic fixtures with
constructed aspect-direction labels, not independent real users or a quality
benchmark. No held-out recommendation success is inferred from them.

The initial rules matched 415 of 500 direction labels, including many easy
neutral snippets. The follow-up safety pass matched 421 (84.2%). Of 72 expected
negative snippets, 35 are now negative and 37 produce no signal; none of these
fixtures are treated as positive. This comes from abstaining on uncertainty cues,
not from reliable sarcasm understanding. There are still 42 missed positive
labels, and cross-sentence references remain unsupported. Clause splitting and
explicit negation have additional regression cases written separately from the
fixture generator. These cases are useful checks, not an independent quality
benchmark. The 0.2-point single-film and 0.7-point overall caps still apply.
Keep feature adjustment offline until separate validation supports deployment.

All synthetic ranking-score changes stayed within the 0.7-point cap. Automated
tests additionally cover duplicate/repeated-word handling, opposing opinions,
low-rating/positive-aspect cases, negated likes, explicit factual mentions,
composer aliases, cross-feature references, and a large ratings-score gap.

## Reproduction

Download the small MovieLens ZIP from the publisher and keep it outside the repo.
The local creative-credit cache must already be populated.

```bash
python scripts/evaluate_movielens.py \
  --zip /path/outside-repo/ml-latest-small.zip \
  --output /path/outside-repo/movielens-text-proxy.json

python scripts/generate_review_scenarios.py
python scripts/test_review_scenarios.py \
  --output /path/outside-repo/synthetic-review-diagnostics.json
```

To add the bounded feature adjustment to a private Letterboxd experiment, pass
`--adaptive-features` to `scripts/evaluate_reviews.py`. The existing TF-IDF and
ratings-only variants stay available for comparison. Nothing in these commands
replaces the saved production model or imports new ratings into its database.

Next: improve recognition of indirect aspect opinions and negation without
making factual or sarcastic mentions positive; expand independently annotated
movie-side music/visual features; and validate on real review-aspect preferences
before selecting influence limits or enabling the feature in the API.


## Catalog and language follow-up

The cached-catalog audit found 314 films, 52 discovery tags, no missing movie
metadata, and no stale flags after tightening phrase boundaries. All 15 films
credited to Hans Zimmer remain outside the default tagged pool. All-catalog
mode makes those films eligible without relabeling them as independent. There
is no guarantee any particular composer will reach the top ten.

Use `scripts/audit_catalog.py --output /tmp/catalog-audit.json` to reproduce the
read-only audit. No ratings, stored classification flags, or saved model were
changed by the audit. Adding more films and source-backed style annotations is
still necessary to improve candidate coverage.

The next evaluation should freeze extraction rules, reserve new profiles for
validation and testing, and tune weights only on validation data. The 500
existing synthetic snippets are development diagnostics; repeated evaluation
on them cannot establish generalization. The production API continues to use
ratings only.

See [separated validation](review-validation.md) for the next run: fresh sparse users favored ratings alone, and new language cases exposed additional errors. The earlier pilot and template scores do not establish deployment readiness.
