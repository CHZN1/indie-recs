"""Conservative, interpretable review features for offline experiments only."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
import unicodedata

from app.review_text import ReviewExample, clean_review

ALIASES = {'hanz zimmer':'hans zimmer', 'wes andersson':'wes anderson'}
FEATURE_PHRASES = {
    'visual:symmetrical framing': ('symmetrical framing', 'symmetric framing', 'symmetry', 'centered framing'),
    'visual:pastel palette': ('pastel palette', 'pastel colors', 'pastel colours', 'pastels'),
    'visual:whimsical production design': ('whimsical production design', 'storybook look', 'storybook aesthetic'),
    'music:jazz percussion': ('jazz percussion', 'jazz drums', 'jazz drumming', 'drum score', 'drum soundtrack'),
}
POSITIVE = re.compile(r"\b(love|loved|like|liked|enjoy|enjoyed|adore|preferred|favorite|favourite|fan|beautiful|gorgeous|lovely|amazing|want|great|excellent|prefer|hypnotic|mesmerizing)\b|\breason i (?:will |ll )?revisit\b|\bwanted more of\b")
NEGATIVE = re.compile(
    r"\b(hate|hated|dislike|disliked|boring|distracting|annoying|overwhelming)\b"
    r"|not (?:a )?(?:[a-z]+ ){0,3}fan"
    r"|(?:not|never|don t|didn t|can t) (?:really )?(?:like|liked|love|loved|enjoy|enjoyed|stand|prefer)"
    r"|not (?:beautiful|gorgeous|lovely|amazing|great|excellent)"
    r"|(?:would not|wouldn t) (?:call|describe|consider) .{0,100}\b(?:great|beautiful|amazing|excellent)\b"
    r"|(?:can t|cannot|couldn t) say (?:i )?(?:liked|enjoyed|loved)\b"
    r"|^\s*not\b|too loud|left me cold|pulling me out of the story"
)
# These cues make literal praise unsafe. Abstain rather than guessing sarcasm.
UNCERTAIN = re.compile(
    r"\b(?:spare me|said absolutely nobody|yeah right|as if|what a surprise|did not need|didn t need|just what i wanted|lucky us)\b"
    r"|\boh great\b|\bbecause apparently\b"
    r"|\b(?:punishment|headache|nothing says|said nobody)\b"
)
NEGATED_NEGATIVE = re.compile(r"\b(?:not|never|don t|didn t) (?:really )?(?:hate|hated|dislike|disliked|boring|annoying|distracting)\b")
NEUTRAL = re.compile(
    r"\b(credits list|someone mentioned|friend mentioned|not composed by|not by|wasn t the composer)\b"
    r"|\b(?:my friend|friends|fans|critics|reviewers|people)\b"
    r"|\b(?:the review|the interview) (?:said|says|mentioned|discussed)\b"
    r"|\b(?:no opinion|no strong feeling|not that i|haven t listened|haven t seen)\b"
)


def normalize(text: str) -> str:
    value = ''.join(c for c in unicodedata.normalize('NFKD', clean_review(re.sub(r'"[^"\n]*"|“[^”\n]*”', "", text))) if not unicodedata.combining(c)).lower()
    value = re.sub(r"[^a-z0-9\s.!?;,]", ' ', value)
    value = re.sub(r'\s+', ' ', value).strip()
    for wrong, right in ALIASES.items():
        value = re.sub(r'\b'+re.escape(wrong)+r'\b', right, value)
    return value


def contains(text: str, phrase: str) -> bool:
    return bool(re.search(r'\b'+re.escape(phrase)+r'\b', text))


@dataclass(frozen=True)
class FeatureCatalog:
    movies: dict[int, frozenset[str]]
    reference_styles: dict[str, list[str]]

    @property
    def people(self):
        return {feature for features in self.movies.values() for feature in features
                if feature.startswith(('composer:', 'director:', 'cinematographer:'))}

    def _features_in(self, clause: str) -> set[str]:
        found = {feature for feature, phrases in FEATURE_PHRASES.items()
                 if any(contains(clause, phrase) for phrase in phrases)}
        style_reference = contains(clause, 'wes anderson') and any(
            contains(clause, phrase) for phrase in ('aesthetic', 'style', 'look', 'vibe'))
        for feature in self.people:
            if style_reference and feature == 'director:wes anderson':
                continue
            if contains(clause, feature.split(':', 1)[1]):
                found.add(feature)
        if style_reference:
            found.update(self.reference_styles.get('wes anderson', []))
        if contains(clause, 'birdman') and any(contains(clause, phrase) for phrase in ('score', 'soundtrack', 'drums')):
            found.update(self.reference_styles.get('birdman', []))
        return found

    def analyze(self, review: ReviewExample) -> dict:
        """Return extracted preferences and a trace of conservative scope decisions.

        A preceding feature can resolve a short first-person reaction only when
        it explicitly refers back, without introducing another movie aspect.
        This limited rule is not general coreference or sarcasm understanding.
        """
        text = normalize(review.text)
        if UNCERTAIN.search(text):
            return {'features': {}, 'decisions': [{'clause': text, 'reason': 'uncertain_tone', 'features': []}]}
        evidence = defaultdict(list)
        decisions = []
        previous = set()
        # Contrasts separate aspect opinions. Commas and sentence boundaries
        # remain visible to avoid borrowing sentiment from unrelated sentences.
        parts = re.split(r'([.!?;,]|\b(?:but|although|however|and|beside|whereas|while|despite)\b)', text)
        boundary = ''
        for part in parts:
            clause = part.strip()
            if not clause:
                continue
            if re.fullmatch(r'[.!?;,]|but|although|however|and|beside|whereas|while|despite', clause):
                boundary = clause
                continue
            found = self._features_in(clause)
            own = bool(re.search(r'\bi (?:think|found|feel|love|loved|like|liked|enjoy|enjoyed|prefer|wanted)\b', clause))
            # Reported opinions belong to their speaker. A possessive family
            # member or an explicit reporting verb is evidence of attribution.
            reported = bool(re.search(
                r'\bmy (?:friend|friends|sister|brother|partner|mother|father)\b'
                r'|\b(?:a |the )?(?:blogger|critic|reviewer|director|interviewer)\b.*\b(?:said|says|called|thinks|loves|liked)\b', clause))
            reason = None
            if reported or NEUTRAL.search(clause):
                reason = 'reported_or_neutral'
            elif re.search(r'\b(?:enjoyed|liked|loved) (?:it |the film |the movie )?(?:for|because of) (?:its |the )?(?:acting|cast|story|plot|editing)\b', clause):
                reason = 'unrelated_aspect'
            elif NEGATED_NEGATIVE.search(clause):
                reason = 'ambiguous_negation'
            inherited = False
            if not found and own and previous and reason is None:
                refers_back = bool(re.search(r'\b(?:it|its|his|her|that)\b', clause))
                competing = bool(re.search(r'\b(?:acting|cast|story|plot|ending|dialogue|costumes|editing)\b', clause))
                specific = bool(re.search(r'\b(?:score|music|contribution|framing|palette|soundtrack|style)\b', clause))
                # Across sentences, an unqualified "it" could mean the film.
                if refers_back and not competing and (boundary not in '.!?' or specific):
                    found = set(previous)
                    inherited = True
            negative = bool(NEGATIVE.search(clause))
            positive = bool(POSITIVE.search(clause))
            if not found and reason is None:
                reason = 'no_supported_feature'
            if reason is None and not positive and not negative:
                reason = 'no_explicit_preference'
            if reason is None:
                sign = -1 if negative else 1
                strength = max(.2, abs(review.rating - 5) / 5)
                for feature in found:
                    evidence[feature].append(sign * strength)
                reason = 'negative_preference' if negative else 'positive_preference'
            decisions.append({'clause': clause, 'reason': reason,
                              'features': sorted(found), 'inherited_reference': inherited})
            # Only one explicitly identified topic can be carried. A style
            # bundle has multiple traits and is deliberately not resolved here.
            previous = found if len(found) == 1 else set()
            boundary = ''
        return {'features': {feature: sum(values) / len(values) for feature, values in evidence.items()},
                'decisions': decisions}

    def extract(self, review: ReviewExample) -> dict[str, float]:
        return self.analyze(review)['features']

    def preferences(self, reviews: list[ReviewExample]) -> tuple[dict[str,float],dict[str,int]]:
        observations = defaultdict(dict)
        for review in reviews:
            for feature,value in self.extract(review).items():
                if abs(value)>1e-12:
                    observations[feature][review.item_id] = value
        preferences, supports = {}, {}
        for feature, by_movie in observations.items():
            values=list(by_movie.values())
            preference=sum(values)/len(values)
            if abs(preference)>1e-12:
                preferences[feature]=preference
                supports[feature]=abs(sum(v>0 for v in values)-sum(v<0 for v in values))
        return preferences,supports

    def scores(self, reviews: list[ReviewExample], candidates: list[int]) -> tuple[dict[int,float],dict]:
        preferences,supports=self.preferences(reviews)
        norm=sum(abs(v) for v in preferences.values())
        scores={item:sum(v for f,v in preferences.items() if f in self.movies.get(item,()))/norm if norm else 0.0
                for item in candidates}
        repeated=max(supports.values(),default=0)
        allowance=min(.7,.2+.1*(repeated-1)) if repeated else 0.0
        return scores,{'preferences':preferences,'distinct_movie_support':supports,
                      'max_adjustment_points':round(allowance,3)}

    def adjust(self, cf: dict[int,float], reviews: list[ReviewExample]) -> tuple[dict[int,float],dict]:
        affinity,evidence=self.scores(reviews,list(cf))
        allowance=evidence['max_adjustment_points']
        return {item:max(0,min(10,value+allowance*affinity[item])) for item,value in cf.items()},evidence
