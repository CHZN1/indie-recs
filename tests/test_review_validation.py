import pytest
from scripts.validate_review_models import select_method, paired_interval, DEVELOPMENT_USERS, VALIDATION_USERS


def report(scores):
    return {'aggregate':{name:{'ndcg_at_10':value} for name,value in scores.items()}}


def test_selection_uses_validation_user_means_and_prefers_ratings_on_ties():
    tied=report({'ratings_svd':.3,'hybrid_0.25':.3,'hybrid_0.5':.3,'hybrid_0.75':.3})
    assert select_method([tied])[0]=='ratings_svd'
    strong=report({'ratings_svd':.2,'hybrid_0.25':.3,'hybrid_0.5':.6,'hybrid_0.75':.4})
    assert select_method([tied,strong])[0]=='hybrid_0.5'
    assert set(DEVELOPMENT_USERS).isdisjoint(VALIDATION_USERS)


def test_paired_bootstrap_resamples_users_not_individual_folds():
    rows=[report({'ratings_svd':.5,'hybrid_0.5':.2}),report({'ratings_svd':.5,'hybrid_0.5':.4})]
    result=paired_interval(rows,'hybrid_0.5')
    assert result['mean']==pytest.approx(-.2)
    assert result['user_differences']==pytest.approx([-.3,-.1])
    assert result['bootstrap_95_percent_interval']==pytest.approx([-.3,-.1])
