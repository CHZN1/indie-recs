# Real review data and evaluation

Synthetic language cases helped diagnose failures, but are not independent evidence of recommendation quality. Real review data is available; users do not need to supply a labeled corpus.

## Sources

- [Cornell movie-review polarity](https://www.cs.cornell.edu/people/pabo/movie-review-data/): the downloaded polarity v2 archive contains 1,000 positive and 1,000 negative reviews. Useful for overall sentiment; it does not label music, visual style, or composer preferences.
- [Amazon review datasets](https://mcauleylab.ucsd.edu/public_datasets/data/amazon/index_snap.html): the downloaded Instant Video five-core subset contains 37,126 nonempty review texts from 5,130 users across 1,685 products. Those counts were measured from the downloaded file. It includes TV and product/playback feedback, which require filtering. Product ratings are not aspect sentiment labels. ASINs must be mapped to films with verified identities before recommendation evaluation. [Amazon Reviews 2023](https://amazon-reviews-2023.github.io/) offers a larger Movies and TV collection for later work.
- [Annotated POM](https://github.com/eusip/POM): human annotations cover opinion targets and polarity, including atmosphere, composers, music, and visual effects. Annotators used review transcripts. This is the most directly relevant source for testing aspect interpretation. Access requires registration and license review; it has not been downloaded or used to train this project.
- [Stanford IMDb](https://ai.stanford.edu/~amaas/data/sentiment/): 50,000 labeled reviews with an existing train/test split. Another overall sentiment benchmark, not a user-history or aspect-label benchmark. Not downloaded yet.

## Next evaluation

Keep the current language extractor frozen. Establish overall sentiment baselines with Cornell, then evaluate aspect extraction against independently annotated POM if access terms permit. Separate reviews by reviewer and film where identifiers allow it, reserve an untouched final test, and report wrong polarity, missed opinions, and neutral false positives.

For recommendation quality, filter Amazon reviews, verify movie identities, and compare ratings alone against ratings plus review text on future held-out interactions. Keep rating influence dominant and measure whether text actually improves ranking. Success on overall sentiment alone does not demonstrate better personalized recommendations.

Downloaded data, private exports, database files, and model artifacts stay outside the public upload package. Dataset availability does not establish commercial redistribution rights. Review each source's terms before shipping a trained product or publishing data. Prefer published corpora to a new scraper; [IMDb](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX) and [Letterboxd](https://letterboxd.com/legal/terms-of-use/) restrict automated collection.

## First trained baseline (2026-10-08)

Run `scripts/train_review_sentiment.py` with `--cornell`, `--amazon`, and an external `--output-dir`. It saves two TF-IDF unigram/bigram logistic-regression models and a source-hashed JSON report outside the repository. Vocabulary fitting uses training reviews only. Configuration and seed were fixed before the run.

Cornell used a stratified 80/20 review split: 86.0% accuracy on 400 test reviews (macro F1 0.860). Reviewer and film separation is not verified for this corpus. Amazon removed three-star reviews and duplicate/empty text, then separated 4,104 training reviewers from 1,026 test reviewers. Its 6,784 test reviews gave 92.17% accuracy, but an always-positive baseline gets 88.75%. Balanced accuracy was 65.78%, macro F1 0.717, and negative recall only 31.72% (242 of 763).

The Amazon model scored 74.0% on the same 400-review Cornell test partition without training on Cornell. This transfer result and the weak negative recall show that headline Amazon accuracy is not sufficient for automatic preference inference. These are now reported, consumed test sets; future model selection needs validation data and a new final holdout.

These models classify overall sentiment. They do not identify which composer or aesthetic a reviewer likes, and they have not replaced the live SVD recommender. Personalized ranking improvement remains unmeasured until movie identities, review histories, and target interactions are prepared.

## Real-history ranking comparison (2026-10-08)

`scripts/evaluate_amazon_reviews.py` compares the SVD ratings baseline with a bounded TF-IDF review-text blend using Amazon ASINs. The published Instant Video metadata download contains 30,648 ASIN/category records but no titles, years, descriptions, or movie/TV distinctions. It cannot support a verified TMDB join. This experiment therefore stays in the original mixed video-product catalog and does not import Amazon products into the live indie catalog.

Global chronological boundaries divide the 37,126 interactions into 22,174 training, 7,493 validation, and 7,459 test rows. Equal timestamps stay in the same partition. The training catalog contains 1,508 products. Neither validation nor test reviews enter item documents, vocabulary fitting, user profiles, or SVD training. Both evaluations use identical earlier training histories; the model is not refit on validation data.

Item text aggregates earlier reviews. User text profiles weight their earlier reviews by their ratings, with three-star reviews contributing zero and lower ratings contributing negative weights. Fixed blends of 0, 5, 10, and 20 percent text are compared. Ranking uses percentiles, so 20 percent is a blend coefficient, not a calibrated probability or fraction of causal influence. Validation NDCG selected 20 percent on a fixed hash sample of 500 users.

On a separate chronological test sample of 1,000 eligible users, ratings alone achieved NDCG@10 0.00703, recall@10 0.01450, and hit@10 0.029. The selected blend achieved 0.02135, 0.03841, and 0.067 respectively. Paired user-bootstrap 95 percent interval for the NDCG difference was [0.00937, 0.01896]. This interval addresses sampled-user variation, not model-seed or dataset uncertainty.

Eligibility requires at least one training interaction and one later unseen product rated at least four stars in the training catalog. The test population included 158 users with one earlier rating, 658 with two to five, and 184 with six or more. These counts do not establish separate performance within each bucket. There were 2,019 test interactions on cold products, excluded from this warm-item comparison. Candidates include every training product not already rated by the user, not sampled negatives. Unrated candidates are unknown preferences.

The improvement is promising but absolute hit rates remain low. It is not an aspect-sentiment evaluation, indie-film benchmark, or proof that a production recommendation service improves. Earlier sentiment experiments used some of these reviews, so this is not untouched data across the project's entire research history. Future tuning needs a fresh final holdout. The live model remains unchanged.

POM registration explicitly asks for research-only use and license acceptance, plus affiliation and contact information. Aspect-label evaluation remains pending access; do not infer gold aspect labels from Amazon star ratings or automatically accept terms on a user's behalf.

## Follow-up robustness test

The stronger-baseline test found a validation-selected 5 percent review blend improves ranking over item-item ratings similarity on 759 previously unreported ranking users. It did not establish that personal review wording is better than a profile built from other reviewers' product descriptions. See [protocol and results](amazon-hybrid-validation.md). This replaces the original SVD-only comparison as the more informative evidence for retaining bounded text in research.
