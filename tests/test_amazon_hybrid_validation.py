import numpy as np
from scripts.validate_amazon_hybrid import populations, ranked, paired


def test_reserved_population_excludes_old_users_cold_items_and_seen_products():
    histories={'old':[{'asin':'a'}],'new':[{'asin':'a'}],'seen':[{'asin':'a'}]}
    rows=[{'reviewerID':'old','asin':'b','overall':5},{'reviewerID':'new','asin':'b','overall':4},{'reviewerID':'seen','asin':'a','overall':5},{'reviewerID':'new','asin':'cold','overall':5}]
    assert populations(rows,histories,{'a':0,'b':1},excluded={'old'})==[('new',{'b'})]


def test_ties_receive_equal_percentile_and_zero_difference_interval():
    assert np.allclose(ranked([3,3,5]),[.25,.25,1])
    result=paired([[.2,0,0],[.3,0,0]],[[.2,0,0],[.3,0,0]])
    assert result['ndcg_difference']==0 and result['bootstrap_95_interval']==[0,0]
