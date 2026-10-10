import numpy as np
import pandas as pd
import pytest
from types import SimpleNamespace
from app.review_text import ReviewExample, ReviewTextModel, blend_scores, ranking_metrics, clean_review
from scripts import evaluate_reviews


def test_specific_review_terms_change_ranking_and_one_review_is_enough():
    model = ReviewTextModel({1:'dreamlike lighting atmospheric shadows',
                             2:'orchestral soundtrack composer violin',
                             3:'bank robbery police chase'})
    lighting = model.scores([ReviewExample(99,9,'Loved the dreamlike lighting')])
    music = model.scores([ReviewExample(99,9,'Loved the orchestral soundtrack')])
    assert lighting[1] > lighting[2] and music[2] > music[1]
    assert model.explain([ReviewExample(99,9,'dreamlike lighting')],1)


def test_low_rating_reduces_matching_content_score():
    model = ReviewTextModel({1:'orchestral music violin',2:'police robbery chase'})
    assert model.scores([ReviewExample(9,2,'orchestral music')])[1] < 0


def test_no_review_signal_preserves_cf_order_and_weight_validation():
    cf={1:8,2:9,3:7}
    assert sorted(blend_scores(cf,{1:0,2:0,3:0},.75),key=blend_scores(cf,{1:0,2:0,3:0},.75).get)==[3,1,2]
    with pytest.raises(ValueError):blend_scores(cf,{1:0},.25)
    with pytest.raises(ValueError):blend_scores(cf,{1:0,2:0,3:0},1.1)


def test_unknown_terms_and_html_do_not_enter_vocabulary():
    model=ReviewTextModel({1:'lighting shadows',2:'music violin'})
    assert np.linalg.norm(model.profile([ReviewExample(1,9,'zzsecretmarker')]))==0
    assert 'zzsecretmarker' not in model.vectorizer.vocabulary_
    assert clean_review('<p>music &amp; violin</p>').strip()=='music & violin'


def test_tie_metrics_do_not_depend_on_movie_id():
    metrics=ranking_metrics({1:0,2:0,3:0},2,k=1)
    assert metrics['rank']==2
    assert metrics['hit_at_10']==pytest.approx(1/3)
    assert metrics['mrr']==pytest.approx((1+1/2+1/3)/3)


def test_leave_one_out_removes_held_out_rating_and_review(monkeypatch):
    frame=pd.DataFrame([['me',1,9],['me',2,8],['other',1,7],['other',3,6]],
                       columns=['user_id','item_id','rating'])
    movies=[SimpleNamespace(id=i,title=str(i),is_indie=True) for i in [1,2,3]]
    docs={1:'lighting shadows',2:'music violin',3:'police chase'}
    reviews=[ReviewExample(1,9,'lighting'),ReviewExample(2,8,'music')]
    real_model=ReviewTextModel
    calls=[]
    class SpyModel(real_model):
        def scores(self,examples,source='reviews'):
            if source=='reviews':calls.append([r.item_id for r in examples])
            return super().scores(examples,source)
    real_svd=evaluate_reviews.SVD
    trainsets=[]
    class SpySVD(real_svd):
        def fit(self,trainset):
            pairs={(trainset.to_raw_uid(u),trainset.to_raw_iid(i)) for u,i,r in trainset.all_ratings()}
            trainsets.append(pairs)
            return super().fit(trainset)
    monkeypatch.setattr(evaluate_reviews,'ReviewTextModel',SpyModel)
    monkeypatch.setattr(evaluate_reviews,'SVD',SpySVD)
    report=evaluate_reviews.evaluate(frame,movies,docs,reviews,'me')
    assert calls[:2]==[[2],[1]]
    assert ('me',1) not in trainsets[0] and ('other',1) in trainsets[0]
    assert ('me',2) not in trainsets[1]
    assert ('me',1) in trainsets[2] and ('me',2) in trainsets[2]
    assert report['reviews_tested']==2
    assert all(f['candidate_count']==2 for f in report['folds'])


def test_composer_name_can_match_without_inventing_music_style():
    model=ReviewTextModel({1:'original music composer Ada Example',
                           2:'original music composer Ben Someone'})
    scores=model.scores([ReviewExample(99,9,'Ada Example composed a wonderful score')])
    assert scores[1]>scores[2]
    assert model.scores([ReviewExample(99,9,'dreamlike lighting')])=={1:0,2:0}


def test_full_vocabulary_does_not_drop_existing_terms_when_metadata_expands():
    original=ReviewTextModel({1:'atmospheric lighting',2:'violin soundtrack'},max_features=None)
    expanded=ReviewTextModel({1:'atmospheric lighting original music composer Ada Example',
                              2:'violin soundtrack director of photography Ben Someone'},max_features=None)
    assert original.vectorizer.vocabulary_.keys() <= expanded.vectorizer.vocabulary_.keys()
