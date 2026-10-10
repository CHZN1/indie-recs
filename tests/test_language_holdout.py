import hashlib
import json
from pathlib import Path
import pytest
from scripts.evaluate_language_holdout import summarize, verify_freeze


def test_metrics_keep_abstention_and_wrong_preferences_separate():
    rows=[{'expected':1,'actual':1},{'expected':-1,'actual':0},
          {'expected':-1,'actual':1},{'expected':0,'actual':-1},
          {'expected':0,'actual':0}]
    result=summarize(rows)
    assert result['correct_labels']==2
    assert result['missed_preferences']==1
    assert result['wrong_sign_preferences']==1
    assert result['preferences_from_neutral_text']==1
    assert result['emitted_preference_precision']==pytest.approx(1/3)
    assert result['intended_preference_recall']==pytest.approx(1/3)


def test_freeze_rejects_changed_dependencies(tmp_path):
    file=tmp_path/'rules.py';file.write_text('frozen')
    manifest={'rules.py':hashlib.sha256(file.read_bytes()).hexdigest()}
    verify_freeze(tmp_path,manifest)
    file.write_text('changed')
    with pytest.raises(ValueError,match='Frozen dependencies changed'):
        verify_freeze(tmp_path,manifest)


def test_holdout_wording_does_not_duplicate_development_cases():
    root=Path(__file__).resolve().parents[1]
    fresh=json.loads((root/'sample_data/review_holdout_v2.json').read_text())['cases']
    old=json.loads((root/'sample_data/review_validation_cases.json').read_text())['cases']
    assert len(fresh)==40 and len({r['id'] for r in fresh})==40
    assert {r['text'].strip().lower() for r in fresh}.isdisjoint(r['text'].strip().lower() for r in old)
