# Stronger ratings baselines and review-text controls

This research test addresses whether the earlier review-text improvement survives a stronger ratings-only comparison. It stays in Amazon ASINs and does not change the live recommendation API.

## Protocol

Run `scripts/validate_amazon_hybrid.py` with `--reviews` and an external `--output`. No reviews or individual reviewer identifiers are bundled in this repository.

The fixed training period is the earlier 60 percent of interactions. Validation is the next 20 percent. Test is the last 20 percent. Equal timestamps stay together. Vocabulary, item text, user review profiles, and ratings models are fitted from the training period only.

Validation uses the same deterministic 500-user sample as the earlier ranking experiment. The new test population excludes the earlier experiment's 1,000 test users and every validation-evaluated user. It uses up to 1,000 other eligible users in a fixed hash order. These users were not previously reported as ranking test users, though the dataset has already been used in sentiment experiments.

Ratings-only alternatives are positive-rating popularity, item-item cosine similarity from positive ratings, and SVD with 100 factors/regularization 0.02 or 20 factors/regularization 0.1, each at seeds 42, 7, and 2026. SVD runs 30 epochs. The validation metric selects the strongest ratings baseline and the strongest candidate among those baselines and their 5, 10, or 20 percent review-text blends. Zero percent text is available, so selection can reject text.

All training products not previously rated by a viewer are ranked. Evaluation counts future unseen warm products rated four or five stars as positives. Unknown preferences among unrated products remain a limitation. Test metrics include NDCG, recall, and any-positive hit rate at ten, with paired user-bootstrap intervals for NDCG differences.

The selected hybrid is compared with two controls at its same base model and coefficient: a profile built from earlier reviews of previously rated products, rather than the viewer's own words, and a fixed shuffled association between candidate products and text scores. The first control still uses review text from other people. It is not a ratings-only baseline. These comparisons help distinguish individual writing signals from general product similarity and chance score perturbations.

Report one-rating, two-to-five-rating, and six-or-more-rating populations separately. Seed sensitivity uses the predetermined 20 percent blend within each SVD configuration. Test results do not select new parameters.

## Limits

The catalog includes movies and TV products, without usable title metadata or verified TMDB identities. Product reviews may discuss playback or purchasing. No aspect labels establish whether music, a director, or lighting is liked or disliked. Confidence intervals reflect sampled users, not product clustering, dataset transfer, or every model's uncertainty. These comparisons cannot establish global optimality or prove that review text can never help.

## Results

The reserved test population contained 759 eligible users after exclusions. Validation selected item-item cosine as the strongest ratings-only baseline and the same baseline with a 5 percent review-text blend as the strongest hybrid.

Ratings alone achieved NDCG@10 0.05128, recall@10 0.08374, and hit@10 13.44 percent. The selected hybrid achieved 0.06495, 0.10092, and 15.68 percent respectively. The NDCG gain was 0.01367, or about 26.7 percent relative to the stronger baseline. Its paired user-bootstrap 95 percent interval was [0.00718, 0.02036]. This supports improvement in this benchmark; it does not establish performance in our indie catalog.

The weaker original SVD baseline achieved NDCG@10 0.00918 on these users. Item similarity alone was already much better, so comparing only with the original SVD would exaggerate the practical value of text. Popularity achieved 0.02612. Both SVD configurations were evaluated at three random seeds, and every fixed 20 percent text blend improved within its corresponding SVD baseline; Three of the six seed/configuration intervals include zero, so consistent positive point estimates are not independently significant in every run. This does not make those weaker baselines competitive with item similarity.

The selected hybrid's descriptive NDCG by history size was 0.04267 versus 0.04024 for one earlier rating (127 users), 0.06650 versus 0.05079 for two to five ratings (490 users), and 0.07952 versus 0.06285 for six or more (142 users). These subgroup point estimates do not establish statistically reliable improvement in each group. Recommendations remain available with one rating.

The same 5 percent blend using text from earlier reviews of previously rated products achieved NDCG@10 0.06734. The personal-review hybrid minus this control had interval [-0.00800, 0.00298], so superiority of the viewer's own writing was not demonstrated. The shuffled-text control achieved 0.03194, below ratings alone. Correct product/text associations matter; any random score perturbation does not explain the gain. Some gain can also come from breaking ties among item-similarity scores.

Keep bounded text as an experimental candidate rather than dropping it. Do not enable automatic aspect preference inference on this evidence. Before promoting a model into the indie API, verify movie identities and catalog eligibility, compare against the stronger item-similarity baseline on movie histories, and validate aspect sentiment independently. No claim that all possible alternatives have been exhausted is justified.

Aggregate results, source hash, and evaluator hash are saved in `research/amazon_hybrid_validation.json`. It contains no raw reviews or reviewer identifiers. Parameter selection was completed on validation before reporting the reserved test. These reported test users are now consumed; future tuning requires another holdout.
