#!/usr/bin/env python3
"""Join published IMDb review histories to cached movie IDs without title guessing."""
import argparse, gzip, hashlib, json, sys, zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.database import SessionLocal
from app.models import Movie, TmdbCache
from app.discovery import decision


def parse_date(value):
    for fmt in ('%d %B %Y','%Y-%m-%d','%d %b %Y'):
        try:return int(datetime.strptime(value,fmt).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:pass
    raise ValueError('Unsupported review date')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args()
    root=Path(__file__).resolve().parent.parent
    if a.output_dir.resolve().is_relative_to(root):ap.error('Keep research data outside public repo')
    a.output_dir.mkdir(parents=True,exist_ok=True);mapping={};ambiguous=set();catalog=[]
    with SessionLocal() as db:
        for m in db.scalars(select(Movie).order_by(Movie.id)):
            row=db.get(TmdbCache,f'movie:{m.tmdb_id}')
            if not row:continue
            b=json.loads(row.payload);iid=b.get('details',{}).get('imdb_id')
            if not iid:continue
            if iid in mapping:ambiguous.add(iid)
            mapping[iid]={'tmdb_id':m.tmdb_id,'title':m.title,'year':m.year,'is_indie':m.is_indie,'discovery':decision(m,b)}
        for iid in ambiguous:mapping.pop(iid,None)
    counts=Counter();users=set();films=set();seen=set()
    with zipfile.ZipFile(a.archive) as z:
        details={r['movie_id']:r for r in map(json.loads,z.open('IMDB_movie_details.json'))}
        accepted={}
        for iid,m in mapping.items():
            d=details.get(iid)
            if not d:continue
            year=int(d['release_date'][:4]) if str(d.get('release_date',''))[:4].isdigit() else None
            if not year or not m['year'] or abs(year-m['year'])>1:counts['year_conflicts']+=1;continue
            accepted[iid]=m;catalog.append({'imdb_id':iid,**m,'dataset_release_date':d['release_date']})
        with gzip.open(a.output_dir/'movie-histories.json.gz','wt',encoding='utf8') as out:
            for line in z.open('IMDB_reviews.json'):
                r=json.loads(line);counts['source_reviews']+=1
                if r['movie_id'] not in accepted:continue
                counts['matched_before_validation']+=1
                try:
                    rating=float(r['rating']);ts=parse_date(r['review_date'])
                    if not 1<=rating<=10 or not r.get('user_id') or not r.get('review_text','').strip():raise ValueError('Invalid rating/user/text')
                except (ValueError,TypeError,KeyError):counts['invalid_rows']+=1;continue
                key=(r['user_id'],r['movie_id'])
                if key in seen:counts['duplicate_pairs']+=1;continue
                seen.add(key);m=accepted[r['movie_id']];users.add(r['user_id']);films.add(r['movie_id'])
                out.write(json.dumps({'reviewerID':r['user_id'],'asin':str(m['tmdb_id']),'overall':rating/2,'unixReviewTime':ts,'reviewText':r['review_text']},ensure_ascii=False)+'\n');counts['accepted_reviews']+=1
    manifest={'source':'https://www.kaggle.com/datasets/rmisra/imdb-spoiler-dataset','archive_sha256':hashlib.sha256(a.archive.read_bytes()).hexdigest(),'join':'Exact cached TMDB details imdb_id plus release year within one year; no title fuzzy match','counts':dict(counts),'users':len(users),'reviewed_movies':len(films),'matched_catalog_movies':len(catalog),'indie_candidates':sum(m['is_indie'] and m['discovery']['eligible'] for m in catalog),'expanded_candidates':sum(m['discovery']['eligible'] for m in catalog),'catalog':catalog,'limits':['Only overlap with current local catalog; not representative of all indie films.','Local cached IMDb links are metadata, not independent manual identity certification.','Data kept for research outside public repository; commercial rights not established.']}
    (a.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps({k:v for k,v in manifest.items() if k!='catalog'},indent=2))
if __name__=='__main__':main()
