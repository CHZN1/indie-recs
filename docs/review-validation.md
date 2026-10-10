# Review modeling validation

The first separated validation/test run does not support enabling review reranking.
The ratings-only API and both discovery options remain available. No private
Letterboxd data, live ratings, or saved model changed during this evaluation.

## Protocol

We freeze the current feature extractor and select a TF-IDF blend using only
validation users. Ratings alone is a candidate alongside 25%, 50%, and 75% text.
Selection uses mean NDCG at ten, with equal weight per user; a tie favors ratings.
After selection, only the chosen blend is evaluated against ratings on fresh test
users. We do not choose a different weight by inspecting test results.

MovieLens users 62, 424, and 474 belong to development; users 477, 537, and 567
belong to validation. All six were explored in the earlier pilot. Users 103, 184,
193, 357, 435, and 599 were not previously evaluated; each has two films with
mapped ratings and tags. Their histories make this a useful sparse-profile test,
but also differ from the larger validation histories. This is a new user test
inside an already explored dataset, not a wholly untouched external benchmark.

For each held-out liked film (rating at least 8/10), we remove that user's rating
and all their tags for the film. Other users' ratings remain in training. The
candidate pool includes unviewed catalog films plus the target. Ties use expected
ranking metrics. Metadata is retrospective, so this is not a temporal evaluation.
The source ZIP and extractor hashes are recorded in the private run report.

## Result

Validation selected the 50% text blend. On six fresh users and eleven liked
targets, ratings-only achieved user-averaged top-ten hit rate 41.7% and NDCG@10
0.27069; the selected blend achieved 16.7% and 0.10742. Mean target rank was
79.75 for ratings and 91.25 for the blend (lower is better).

The paired user-averaged NDCG difference was -0.16326. A descriptive bootstrap
interval, resampling six users 10,000 times, was [-0.32178, -0.04404]. Six
convenience-sampled users cannot establish performance for the general population.
Unrated films have unknown relevance, and tags are short descriptions rather
than full reviews. The bounded aspect extractor found no supported opinions in
these tags and exactly preserved ratings-only results. That does not validate
composer or aesthetic personalization.

## New language challenge

We authored 24 new snippets after development, covering explicit opinions,
negation, mixed aspects, factual attribution, sarcasm, and indirect preferences.
We scored them without modifying the extractor. Ten direction labels matched;
eight intended preferences produced no signal, and six negative or neutral
labels were treated as positive. Ordinary explicit opinions passed all four
cases, but harder phrasing exposed unsafe sentiment scope and negation errors.

These original synthetic labels are not independent human judgments. Once
inspected, the cases become development diagnostics and must not be called a
fresh holdout again. The older 500 snippets also remain development fixtures.
High scores on familiar templates do not establish language understanding.

## Reproduce

Keep the research-only dataset and detailed run reports outside the repository.
Use the same catalog and cached metadata to reproduce the exact run; catalog
changes can affect candidate ranks.

```bash
python scripts/validate_review_models.py --zip /tmp/ml-latest-small.zip --output /tmp/review-validation.json
python scripts/validate_review_language.py --output /tmp/review-language-validation.json
```

See [preference research](preference-research.md) for data provenance and licensing.
No new production dependency or network call is required by these scripts.

## Next work

Improve aspect attribution and negation using the newly exposed failures as
regressions. Likely sarcasm should continue to produce no signal. Then reserve
another unseen set of language cases and, ideally, real full reviews with movie
and user identifiers plus appropriate research permissions. The current test
users are now consumed as a holdout; future tuning requires another split.

Review import/storage and an optional demo mode follow that quality gate. Weight
limits remain heuristic. We will retain ratings-only as the default unless a
new evaluation supports the review model. Authentication, profile ownership,
training jobs, and deployment remain later roadmap items.


## Language repair pass — October 8, 2026

The initial 24 challenges are now consumed development cases. The repair pass
handles never/did-not negation, "wouldn't call ... great," comma contrasts, and
separate opinions about different aspects. It excludes quoted praise and reported
opinions from friends, fans, and critics. Separate first-person clauses can still
supply evidence. Double negatives such as "I didn't dislike" produce no signal
rather than being guessed as either praise or dislike.

A small set of direct preference phrases, such as "the reason I'll revisit" and
"wanted more of," now provides evidence. "Stayed with me for days" remains
ambiguous, since memorable experiences can be positive or negative. Sarcasm cues
still cause abstention. The rules do not provide general language understanding.

On the original labels, the updated extractor matches 19/24, compared with
10/24 before repair. It produces no positive preferences for the known negative
or neutral challenges. The five unmatched labels are four sarcastic opinions
and one ambiguous indirect statement; all produce no signal. We preserve those
original labels rather than redefining abstention as correct understanding.
The 500 older development snippets still match 421 labels; their influence-cap
checks also pass. Neither score is new validation evidence.

Regression tests cover the consumed challenges, quoted speech, other speakers,
double negatives, and separate first-person opinions. The production API remains
ratings-only. The next step is to freeze this version before creating and scoring
another unseen set. No new holdout has been created or evaluated in this repair
pass. General sentiment scope, pronoun references, quoted attribution without
explicit markers, and subtle sarcasm remain limitations.

## Frozen new-wording test — October 8, 2026

After the repair pass, we recorded SHA-256 hashes for the feature extractor,
text preprocessing module, and reference feature definitions. Forty new snippets
were authored and labeled before scoring, with five examples each for explicit
opinions, negation, attribution, mixed aspects, indirect preferences, sarcasm,
neutral mentions, and named references. None duplicates the original 24 cases.
They use the same authoring process as development and are not independent
real-user judgments. The extractor remained unchanged before and after the run.

The diagnostic gate was set before scoring: no wrong-sign preferences, no
preferences inferred from neutral text, and at least 80% recall of intended
preferences. Passing that gate would still require recommendation-quality
validation before deployment.

The result was 25/40 matched labels (62.5%), eight missed preferences, five
wrong-sign preferences, and two preferences inferred from neutral statements.
Of 23 emitted preferences, 16 matched the labels (69.6% precision). Recall of
intended preferences was 16/29 (55.2%). This failed the diagnostic gate.

Examples include "I can't say I liked the jazz percussion" being read as praise
and a blogger's praise being assigned to the reviewer. Subtle sarcastic praise
also produced positive preferences. Cross-sentence pronouns and broader indirect
phrasing often produced no signal. These results show that repairing known
phrases has not produced reliable aspect interpretation.

No rules were modified after viewing this result, and review reranking remains
offline. This set is now consumed: fixes can use it as development evidence,
but it cannot remain an unseen validation set. The next work should address
sentiment scope, reported speech, and pronoun references systematically rather
than adding only the exact failed phrases.

Reproduce the frozen run while the dependency hashes still match:

```bash
python scripts/evaluate_language_holdout.py --freeze research/review_holdout_v2_freeze.json --output /tmp/review-language-holdout-v2.json
```

The script refuses to run when a frozen dependency changes. The original
synthetic cases and hashes may be distributed with the code; detailed local run
reports remain outside the repository. Live ratings and the saved model are
unaffected.

## Opinion-scope repair pass

The extractor now separates feature identification from sentiment decisions and
returns a clause-level trace through `FeatureCatalog.analyze`. Each decision
records a reason such as reported/neutral text, ambiguous negation, unrelated
aspect, uncertain tone, or a supported positive/negative preference. `extract`
continues to return only the preference map, so existing experiment callers work
without API changes. The trace is not stored or served by the production API.

Negated evaluation verbs include "can't say I liked" and "wouldn't describe ...
as beautiful." Reported opinions from family members and explicit blogger or
reviewer statements are excluded. Praise tied to acting does not transfer to a
composer merely because the same sentence mentions a music credit.

A short first-person reaction may borrow one immediately preceding feature when
it refers back explicitly and introduces no competing aspect. Across sentences,
a generic "I liked it" remains too ambiguous to identify a movie feature.
Multiple-feature style bundles, plural references, and intervening topics are
not resolved. Uncertain tone may suppress an entire review; this conservative
choice can discard legitimate opinions as well as sarcastic praise.

On the consumed forty cases, 31 labels now match, twenty intended preferences
are emitted correctly, nine preferences produce no signal, and none is emitted
with the wrong sign or from neutral text. Recall is 20/29 (69.0%), still below the
80% diagnostic threshold. These are development regressions after targeted
repairs, not another holdout result. The older 500 fixtures remain at 421 matched
labels and continue to pass influence-cap checks.

```bash
python scripts/evaluate_language_holdout.py --development --output /tmp/review-scope-development.json
```

The original freeze manifest remains unchanged and intentionally rejects the
current repaired extractor. It records the version used for the historical test;
it is not a freeze for this new version. Original labels and the private
historical report are preserved. A new freeze and unseen cases are required for
future validation. Ratings-only recommendations and both discovery scopes remain
unchanged, and review reranking stays offline.

## Outcome of the next frozen challenge

The 24-case v3 new-wording challenge matched 11 labels, with six wrong-sign preferences, four preferences from neutral text, and three missed preferences. The extractor stayed frozen. It failed the same diagnostic gate. We stopped expanding rules as a path to live automatic reranking and implemented optional explicitly confirmed preferences. See [the decision and integration contract](confirmed-preferences.md). This is the best-supported current design choice, not proof of an optimal automatic model.
