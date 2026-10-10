# Confirmed preferences

The current recommendation default is ratings-only. Automatic review-text
reranking has not passed validation. The optional confirmed-preference mode is a
small, user-controlled ranking adjustment; it does not claim to understand raw
reviews or prove better recommendations.

## Why this approach

Another frozen new-wording challenge, with 24 synthetic cases, matched eleven
labels. It produced six wrong-sign preferences, four preferences from neutral
statements, and three missed preferences. The extractor was unchanged during
scoring. The cases were authored by the same process as development, so they are
not independent human evidence. They are now consumed.

This reinforces the earlier sparse-user MovieLens comparison, where ratings
alone outperformed the validation-selected text blend. Repeatedly adding wording
rules has not demonstrated generalization. We retain the offline extractor and
its decision traces for research, but the live confirmed mode never calls it.

Aspect identification and aspect polarity are separate evaluation tasks in
[SemEval-2014 Task 4](https://aclanthology.org/S14-2004/). Its restaurant/laptop
annotations are not movie user histories and are not used as a movie-ranking
benchmark here. A future learned aspect model requires appropriately labeled
movie reviews and a fresh user-level recommendation evaluation.

## Demo

Open `/demo`, expand **Refine with a confirmed preference**, search for a
composer or trait, choose **Prefer** or **Avoid**, and confirm the choice. Remove
a choice to revert its effect. Choices stay in memory in this browser tab,
reset when switching viewers, and are not saved to the database. Reloading clears
them. No raw reviews or personal exports are transmitted by this feature.

Some composer matches exist only outside the tagged indie pool. Switch to
**Expanded indie discovery** when appropriate. Counts describe the whole catalog,
including already rated films. A match can remain outside the top ten because
ratings remain dominant.

## Integration contract

`GET /preferences/options` lists canonical feature identifiers, labels, full
catalog match counts, and indie match counts. It reads cached TMDB creative
credits and the small source-backed curated trait map. It makes no external API
request. Missing annotations mean unknown, not absence of a trait.

`POST /recommend/{user_id}/preferences?scope=indie` accepts up to eight distinct
confirmed choices. Use `scope=all` for the wider pool.

```json
{
  "choices": [
    {"feature": "composer:hans zimmer", "direction": "prefer"},
    {"feature": "visual:pastel palette", "direction": "avoid"}
  ]
}
```

Unknown features and duplicate choices return HTTP 400. Invalid directions,
extra payload fields, excess choices, or invalid scopes return HTTP 422. The
server treats a choice as a preference explicitly supplied by the client; it is
not proof of an authenticated user's consent. Authentication and profile
ownership still belong to the production roadmap.

For a trained profile, score the entire eligible unseen catalog first, apply
preferences, and then return ten films. Each matching preferred choice adds
`0.2 / number_of_choices`; each matching avoided choice subtracts the same amount.
The combined adjustment is bounded by 0.2 points and scores stay between 0 and
10. Opposing matches cancel. This is a conservative heuristic, not a validated
optimal weight. Repeated review keywords do not enlarge this cap because raw
reviews are not an input to the live mode.

`predicted_rating` preserves the original SVD estimate. `ranking_score`,
`preference_adjustment`, and `preference_matches` explain the separate ordering
change. The response uses `preference_mode: confirmed` when applied. Empty choices
preserve baseline ordering. An untrained user retains the original popular-film
fallback with `preference_mode: ratings_only`; manual adjustments are not applied
to that fallback. Watched-film exclusion and discovery scope apply in both modes.

The mode is stateless. It does not modify ratings, save a profile, retrain the
model, send review text to a third-party model, or alter the ordinary GET endpoint.

## Film identity corrections

Browser verification found four generated/sample-film identities that resolved
to different same-title movies. The corrected TMDB identifiers are The Witch
310131, Under the Skin 97370, and The Beast 914206, and Crash 1640. The intended movies release in
TMDB in 2016, 2014, 2024, and 2005, while their sample years were 2015, 2013, 2023, and 2004.
Festival and general-release years can differ; title/year alone does not prove
identity. See `research/catalog_identity_repairs.json` for the public identifiers.

Only synthetic/sample profiles rated these entries. A local backup was made
before correction. All 3,667 rating rows and their internal movie identifiers
were preserved, so the saved SVD model remains compatible. Public metadata,
posters, credits, and discovery flags were refreshed for the corrected films.
The local catalog remains 314 movies and now has 53 discovery tags.

Prepared imports support an optional **TMDB ID** column. A nonblank positive ID
bypasses title search and resolves movie metadata directly, so same-title films
stay distinct. Blank values retain legacy search behavior, which is heuristic.
Invalid IDs fail validation before import. The affected sample rows and synthetic
generator now include the verified IDs. These four corrections are not global
aliases; a different same-title movie may be the user's actual intended film.

## Evidence and remaining work

Tests cover full-catalog reranking before cutoff, rating preservation, score
bounds, opposing choices, watched exclusions, scope differences, unknown-profile
fallback, invalid input, and explicit movie-ID import. Discovery exclusions apply before preference reranking, so a confirmed preference cannot reintroduce an excluded blockbuster. Options expose `discovery_matches` alongside `indie_matches` and `catalog_matches`; the demo only offers features with an eligible discovery match.

These checks establish mechanics, not improved satisfaction or globally optimal
recommendations. The next quality work requires independent human aspect labels,
real full-review histories with suitable permissions, and a held-out user test.
The production roadmap still includes authentication, ownership, background
training, deployment, and broader catalog identity review.

The catalog audit also flags cached vote counts below 50 for identity review. Low counts are a triage signal, not proof of an incorrect match. Other films with similar titles may need review; these four corrections do not establish perfect catalog identity coverage.
