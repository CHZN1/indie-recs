from app.indie import classify_indie, indie_evidence


def test_indie_matching_requires_words_and_normalizes_punctuation():
    assert not classify_indie(production_companies=['Neonatal Pictures', 'Magnolias Productions'], genres=[], keywords=[])
    assert classify_indie(production_companies=['IFC-Films'], genres=[], keywords=[])
    assert classify_indie(production_companies=[], genres=[], keywords=["Directors' Fortnight"])
    assert not classify_indie(production_companies=[], genres=['Drama'], keywords=[])


def test_evidence_explains_all_matches_without_declaring_untagged_non_indie():
    assert indie_evidence(production_companies=['A24'], genres=[], keywords=['independent film']) == ['company: A24', 'independent keyword: independent film']
