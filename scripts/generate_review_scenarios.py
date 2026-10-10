#!/usr/bin/env python3
"""Create original, labeled synthetic language fixtures—not a quality benchmark."""
import json
import random
from pathlib import Path

TOPICS = {
 'zimmer': {'feature':'composer:hans zimmer','name':'Hans Zimmer','aspect':"Hans Zimmer's score",'implicit':'The swelling score was my favorite part, especially the Zimmer cues'},
 'anderson': {'feature':'visual:pastel palette','name':'Wes Anderson','aspect':'the Wes Anderson aesthetic','implicit':'Pastel corridors, dead-center frames, dollhouse sets. That is my kind of thing'},
 'birdman': {'feature':'music:jazz percussion','name':'Birdman','aspect':'the Birdman-style drum score','implicit':'Loose jazz percussion, all skittering rhythms and restless energy. More of that, please'},
}
STYLES = {
 'brief': (1,['I love {aspect}.','I enjoyed {aspect}.','Really liked {aspect}.','{aspect} was great.','I am a fan of {aspect}.']),
 'chatty': (1,['Okay, I loved {aspect}. The plot lost me a little, though.', 'Honestly, {aspect} is what I liked most.','I would watch it again for {aspect}. I loved it.','I liked {aspect} way more than I expected.','The ending was a mess, but I loved {aspect}.']),
 'detailed': (1,['I enjoyed {aspect} because it gave the scenes a shape the dialogue never quite found.','I loved {aspect}. It held my attention even when the middle section dragged.','The actors were fine, but I preferred {aspect}. That stayed with me afterward.','I liked the story, and I loved {aspect}. The two worked together for me.','I am a fan of {aspect}; that was a stronger reason to return than the plot.']),
 'mixed_low_rating': (1,['I disliked the story, but I loved {aspect}.','This was boring, but {aspect} was great.','I hated the ending. I enjoyed {aspect}.','The acting left me cold, but I liked {aspect}.','I would not recommend the film overall. I am a fan of {aspect}, though.']),
 'negative': (-1,['I hated {aspect}.','I liked the story, but {aspect} was distracting.','I am not a fan of {aspect}.','I did not enjoy {aspect}.','I did not love {aspect}. The cast was great.']),
 'factual': (0,['The credits list {name}. The ending was good.','Someone mentioned {name}. I liked the acting.','{aspect} comes up in the discussion of this film.','A friend mentioned {name} before we watched it.','The review I read mentioned {aspect}.']),
 'sarcastic': (-1,['Oh great, more {aspect}. Exactly what I did not need.','Amazing, another round of {aspect}. Spare me.','Just what I wanted: {aspect}, again.','Great, {aspect}. What a surprise.','Love that we got more {aspect}. Said absolutely nobody in my house.']),
 'implicit': (1,['{implicit}.','{implicit}. The plot was a different story.','{implicit}. I could have done without the ending.','{implicit}. That part stayed with me.','{implicit}. The dialogue, less so.']),
}
NOISE = ['Good performances. The ending felt rushed.','The central friendship worked for me.','The plot took its time getting anywhere.','I would have cut twenty minutes.','Funny in places, uneven in others.']


def main():
 rng=random.Random(42);profiles=[]
 for index in range(100):
  topic=list(TOPICS)[index%3];style=list(STYLES)[(index//3)%len(STYLES)]
  expected,templates=STYLES[style];count=1+index%5;reviews=[]
  for j in range(5):
   text=templates[j].format(**TOPICS[topic]) if j<count else NOISE[j]
   if index%7==0:text=text.replace('Hans Zimmer','Hanz Zimmer').replace('Wes Anderson','Wes Andersson')
   rating=rng.choice([1,2,3,4]) if style=='mixed_low_rating' else rng.choice([5,6,7,8,9,10])
   reviews.append({'item_id':900000+index*5+j,'rating':rating,'text':text,
                   'expected_direction':expected if j<count else 0})
  profiles.append({'id':f'synthetic-{index+1:03d}','topic':topic,'style':style,
                   'expected_feature':TOPICS[topic]['feature'],'repeated_movies':count,'reviews':reviews})
 out=Path(__file__).resolve().parent.parent/'sample_data'/'review_scenarios.json'
 out.write_text(json.dumps({'synthetic':True,'seed':42,'purpose':'Language robustness and influence controls. Constructed labels are not real user preferences or evidence of recommendation quality.','profiles':profiles},indent=2))
 print(f'Created {len(profiles)} fictional profiles and {len(profiles)*5} original synthetic review snippets.')


if __name__=='__main__':main()
