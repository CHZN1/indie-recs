from types import SimpleNamespace
from app.discovery import decision


def bundle(company,budget=0,collection=None):
    return {'details':{'production_companies':[{'name':company}],'budget':budget,'belongs_to_collection':collection},'keywords':[]}


def test_superheroes_block_even_if_mistagged_indie():
    movie=SimpleNamespace(is_indie=True)
    for c in ['Marvel Studios','Marvel Entertainment','DC Entertainment','DC Studios']:
        assert not decision(movie,bundle(c))['eligible']


def test_large_budget_and_major_franchise_block():
    movie=SimpleNamespace(is_indie=False)
    assert not decision(movie,bundle('FilmNation Entertainment',200_000_000))['eligible']
    assert not decision(movie,bundle('Warner Bros. Pictures',20_000_000,{'id':1}))['eligible']
    assert not decision(movie,bundle('Paramount Pictures',10_000_000))['eligible']


def test_expansion_requires_positive_evidence_not_just_untagged_or_cheap():
    movie=SimpleNamespace(is_indie=False)
    assert not decision(movie,None)['eligible']
    assert not decision(movie,bundle('Unknown',1000000))['eligible']
    assert decision(movie,bundle('FilmNation Entertainment',20000000))['eligible']
    assert not decision(SimpleNamespace(is_indie=True),bundle('A24',50000000))['eligible']
    assert not decision(movie,bundle('FilmNation Entertainment',47000000))['eligible']
    assert decision(SimpleNamespace(is_indie=True),bundle('A24',10000000))['eligible']
