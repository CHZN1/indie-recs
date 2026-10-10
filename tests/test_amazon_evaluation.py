import numpy as np
from scripts.evaluate_amazon_reviews import split_rows, metrics, blend_scores


def test_time_boundaries_do_not_split_same_day_across_partitions():
    rows=[{'unixReviewTime':t,'reviewText':str(t)} for t in [1,2,3,4,5,6,6,8,8,10]]
    train,val,test,c1,c2=split_rows(rows)
    assert max(r['unixReviewTime'] for r in train)<min(r['unixReviewTime'] for r in val)
    assert max(r['unixReviewTime'] for r in val)<min(r['unixReviewTime'] for r in test)
    assert len(train)+len(val)+len(test)==len(rows)


def test_ranking_metrics_respect_multiple_relevant_items_and_cutoff():
    result=metrics(['other','a','b'],{'a','b'},k=2)
    assert result[1]==.5 and result[2]==1
    assert np.isclose(result[0],(1/np.log2(3))/(1+1/np.log2(3)))
    assert metrics(['other'],{'a'})==[0,0,0]


def test_asin_blending_preserves_zero_text_and_bounded_weight():
    cf={'B000A':4,'B000B':3};text={'B000A':0,'B000B':0}
    assert blend_scores(cf,text,.2)==blend_scores(cf,text,0)
    result=blend_scores(cf,{'B000A':0,'B000B':1},.2)
    assert result['B000A']>result['B000B']
