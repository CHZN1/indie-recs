#!/usr/bin/env python3
"""Score consumed language challenge cases as development regressions."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.review_features import FeatureCatalog
from app.review_text import ReviewExample


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parent.parent
    if args.output.resolve().is_relative_to(root):parser.error('Keep run reports outside the repository.')
    fixture=root/'sample_data'/'review_validation_cases.json'
    cases=json.loads(fixture.read_text())['cases']
    reference_styles=json.loads((root/'research'/'curated_features.json').read_text())['reference_styles']
    features=FeatureCatalog({1:frozenset(['composer:hans zimmer','visual:pastel palette','visual:symmetrical framing','music:jazz percussion'])},reference_styles)
    results=[]
    for index,row in enumerate(cases):
        value=features.extract(ReviewExample(100+index,row['rating'],row['text'])).get(row['feature'],0)
        actual=1 if value>0 else -1 if value<0 else 0
        results.append({**row,'actual':actual,'correct':actual==row['expected']})
    groups={g:{'correct':sum(r['correct'] for r in results if r['group']==g),'total':sum(r['group']==g for r in results)} for g in sorted({r['group'] for r in results})}
    report={'phase':'development_regression','extractor_sha256':hashlib.sha256((root/'app/review_features.py').read_bytes()).hexdigest(),
            'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
            'total':len(results),'correct':sum(r['correct'] for r in results),'abstentions':sum(r['actual']==0 for r in results if r['expected']!=0),
            'false_positive_preferences':sum(r['actual']==1 and r['expected']<=0 for r in results),
            'by_group':groups,'results':results,
            'decision':'Do not enable review reranking by default; challenge failures require further development.',
            'limitations':['Original synthetic cases labeled by the same authoring process; not independent real-user judgments.',
                           'These cases have been inspected and used for targeted fixes. Current scores are development regressions, not unseen validation.',
                           'Abstentions avoid some wrong preferences but lose useful information.']}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ['total','correct','abstentions','false_positive_preferences','by_group','decision']},indent=2))


if __name__=='__main__':main()
