import numpy as np
import pytest
from scripts.prepare_imdb_histories import parse_date
from scripts.evaluate_mabsa_aspects import duplicate_groups, labels


def test_source_review_dates_parse_without_machine_timezone():
    assert parse_date('1 January 1970')==0
    assert parse_date('1970-01-01')==0
    with pytest.raises(ValueError):parse_date('unknown')


def test_aspect_duplicate_groups_connect_either_language_and_keep_absent_separate():
    groups=duplicate_groups(['original1','original1','original3'],['English1','English2','English2'])
    assert len(set(groups))==1
    assert labels([np.nan,0,.5,1]).tolist()==['absent','negative','neutral','positive']
