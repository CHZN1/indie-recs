#!/usr/bin/env python3
"""Score an authored holdout with dependency hashes checked before and after."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.review_features import FeatureCatalog
from app.review_text import ReviewExample


def summarize(results):
    intended=sum(r['expected']!=0 for r in results)
    signals=[r for r in results if r['actual']!=0]
    correct=sum(r['actual']==r['expected'] for r in results)
    abstentions=sum(r['actual']==0 and r['expected']!=0 for r in results)
    wrong_sign=sum(r['actual']*r['expected']<0 for r in results)
    neutral_preferences=sum(r['expected']==0 and r['actual']!=0 for r in results)
    correct_signals=sum(r['actual']==r['expected'] for r in signals)
    return {'total':len(results),'correct_labels':correct,'direction_accuracy':correct/len(results),
            'missed_preferences':abstentions,'wrong_sign_preferences':wrong_sign,
            'preferences_from_neutral_text':neutral_preferences,
            'emitted_preferences':len(signals),
            'emitted_preference_precision':correct_signals/len(signals) if signals else None,
            'intended_preference_recall':correct_signals/intended if intended else None,
            'confusion':[{'expected':e,'actual':a,'count':count} for (e,a),count in sorted(Counter((r['expected'],r['actual']) for r in results).items())]}


def verify_freeze(root, manifest):
    changed=[p for p,digest in manifest.items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=digest]
    if changed:raise ValueError('Frozen dependencies changed: '+', '.join(changed))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--development',action='store_true',help='Score consumed cases after fixes; not unseen validation.')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--fixture',type=Path,default=Path('sample_data/review_holdout_v2.json'))
    args=parser.parse_args();root=Path(__file__).resolve().parent.parent
    if args.output.resolve().is_relative_to(root):parser.error('Keep run reports outside the repository.')
    if not args.development and args.freeze is None:parser.error('--freeze is required for a frozen run.')
    manifest=({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ('app/review_features.py','app/review_text.py','research/curated_features.json')}
              if args.development else json.loads(args.freeze.read_text()))
    verify_freeze(root,manifest)
    fixture=args.fixture if args.fixture.is_absolute() else root/args.fixture
    cases=json.loads(fixture.read_text())['cases']
    references=json.loads((root/'research'/'curated_features.json').read_text())['reference_styles']
    catalog=FeatureCatalog({1:frozenset(r['feature'] for r in cases)},references)
    results=[]
    for index,row in enumerate(cases):
        detected=catalog.extract(ReviewExample(index+100,row['rating'],row['text']))
        value=detected.get(row['feature'],0)
        results.append({**row,'actual':1 if value>0 else -1 if value<0 else 0,'detected_features':detected})
    verify_freeze(root,manifest)
    metrics=summarize(results)
    # Predeclared diagnostic gate. Passing would still not prove recommendation quality.
    passed=(metrics['wrong_sign_preferences']==0 and metrics['preferences_from_neutral_text']==0
            and (metrics['intended_preference_recall'] or 0)>=.8)
    report={'run_date':'2026-10-08','phase':'development_regression' if args.development else 'new_wording_frozen_extractor_test',
            'freeze_verified_before_and_after':True,'frozen_dependencies':manifest,
            'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
            'gate':'Zero wrong-sign/neutral preferences and at least 80% recall of intended preferences. Diagnostic only; real recommendation validation is also required.',
            'diagnostic_gate_passed':passed,'summary':metrics,
            'by_group':{g:summarize([r for r in results if r['group']==g]) for g in sorted({r['group'] for r in results})},
            'results':results,'production_decision':'Keep review reranking offline.',
            'limits':['Consumed cases used for targeted repairs; not unseen validation.' if args.development else 'New wording scored without post-result rule changes.',
                      'Original synthetic examples authored by the same process as development cases, not independent human labels.',
                      'These examples test wording, not new users or recommendation relevance.',
                      'After this run, the set is consumed; fixes require another unseen validation set.',
                      'Zero measured false preferences in a sample would not establish general safety.']}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ['freeze_verified_before_and_after','summary','diagnostic_gate_passed','production_decision']},indent=2))


if __name__=='__main__':main()
