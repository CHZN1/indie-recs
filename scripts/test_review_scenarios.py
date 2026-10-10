#!/usr/bin/env python3
"""Measure controlled extraction failures and verify bounded review influence."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Movie,TmdbCache
from app.review_features import FeatureCatalog, normalize
from app.review_text import ReviewExample


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args();root=Path(__file__).resolve().parent.parent
 if args.output.resolve().is_relative_to(root):parser.error('Keep diagnostic reports outside the repository.')
 definitions=json.loads((root/'research'/'curated_features.json').read_text())
 fixture=json.loads((root/'sample_data'/'review_scenarios.json').read_text())
 movie_features={int(i):set(row['features']) for i,row in definitions['movies'].items()}
 titles={int(i):row['title'] for i,row in definitions['movies'].items()}
 indie_ids=set()
 with SessionLocal() as db:
  for movie in db.scalars(select(Movie)):
   titles[movie.tmdb_id]=movie.title
   row=db.get(TmdbCache,f'creative:{movie.tmdb_id}');credits=json.loads(row.payload) if row else {}
   values=movie_features.setdefault(movie.tmdb_id,set())
   for role,label in [('composers','composer'),('directors','director'),('cinematographers','cinematographer')]:
    values.update(f'{label}:{normalize(name)}' for name in credits.get(role,[]))
   if movie.is_indie:indie_ids.add(movie.tmdb_id)
 features=FeatureCatalog({i:frozenset(v) for i,v in movie_features.items()},definitions['reference_styles'])
 results=[];correct=0;total=0;counts={}
 for profile in fixture['profiles']:
  examples=[ReviewExample(r['item_id'],r['rating'],r['text']) for r in profile['reviews']]
  checked=[]
  for row,example in zip(profile['reviews'],examples):
   value=features.extract(example).get(profile['expected_feature'],0)
   direction=1 if value>1e-12 else -1 if value < -1e-12 else 0
   success=direction==row['expected_direction'];correct+=success;total+=1
   record=counts.setdefault(profile['style'],{'correct':0,'total':0});record['correct']+=success;record['total']+=1
   checked.append({'text':row['text'],'expected':row['expected_direction'],'actual':direction,'correct':success})
  cf={i:8.0 for i in features.movies}
  adjusted,evidence=features.adjust(cf,examples)
  assert all(abs(adjusted[i]-cf[i])<=.7+1e-12 for i in cf)
  results.append({'id':profile['id'],'topic':profile['topic'],'style':profile['style'],
                  'repeated_movies':profile['repeated_movies'],'evidence':evidence,'checks':checked,
                  'matching_candidates':[titles[i] for i,v in features.movies.items() if profile['expected_feature'] in v],
                  'indie_matching_candidates':[titles[i] for i,v in features.movies.items() if i in indie_ids and profile['expected_feature'] in v]})
 report={'synthetic':True,'profiles':len(results),'review_snippets':total,'correct_directions':correct,
         'direction_accuracy':round(correct/total,4),'by_style':counts,'results':results,
         'bound':'At most 0.2 rating points for one distinct film; +0.1 per repeated consistent film; cap 0.7 on a 0–10 scale.',
         'limitations':['Constructed lexical fixtures test mechanics, not real recommendation quality.',
                        'Sarcasm, implicit sentiment, cross-sentence references, and sentiment scope are not reliably understood.',
                        'Curated style coverage is tiny and editorial; unannotated films have unknown styles.',
                        'Birdman and Paddington 2 appear as documented research reference candidates; they were not added to the live database.']}
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
 print(json.dumps({k:report[k] for k in ('profiles','review_snippets','correct_directions','direction_accuracy','by_style','bound')},indent=2))


if __name__=='__main__':main()
