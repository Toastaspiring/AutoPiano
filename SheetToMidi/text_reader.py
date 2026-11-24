"""
Reads a score written out by hand as text: for scanned sheets, which have no
music symbols inside to read. See scores/charleston.txt for a full example.

    title Charleston        tempo 190      time 4/4
    swing 0.6               (offbeat eighths fall at 60% of the beat; leave out for straight)
    pedal none              (no sustain pedal; leave out to pedal by bar and chord)
    order 1-36 37-66 5-34   (bars in the order they are played: repeats, D.S., codas)

    bar 5                   then, for that bar:
    section HEAD            a label; phrases are shaped within sections
    chords Bb@0 D7@2        chord symbols at beats (from 0)
    dyn mf@0                pp p mp mf f ff at a beat
    hairpin 1 0 16          cresc (1) or dim (-1) from a beat, lasting that many beats
    fermata 2               hold from that beat to the end of the bar
    R D4+F4:1' r:.5 D4+F4:.5>~ D4+F4:2    right hand
    L = 1                   left hand: the same as in bar 1

A note is pitches joined by + (concert pitch, real accidentals: Bb3, F#4),
then : and its length in beats (1, .5, 1/3), then marks: ' staccato,
> accent, ^ marcato, ~ tied to the next. r:2 is a rest.
"""
import re
from fractions import Fraction

from sheet_reader import Note, Score, merge_ties

STEPS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
TOKEN = re.compile(r"(r|[A-G][#b]?-?\d(?:\+[A-G][#b]?-?\d)*):([\d./]+)([~'>^]*)")


def pitch(name):
    m = re.fullmatch(r'([A-G])([#b]?)(-?\d)', name)
    return 12 * (int(m[3]) + 1) + STEPS[m[1]] + {'#': 1, 'b': -1, '': 0}[m[2]]


def _at(item):
    """'Bb7@2' -> ('Bb7', Fraction(2))"""
    what, _, beat = item.rpartition('@')
    return what, Fraction(beat)


def read_text(path):
    score = Score()
    bars, order, current = {}, None, None
    for number, raw in enumerate(open(path, encoding='utf-8'), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        word, _, rest = line.partition(' ')
        rest = rest.strip()
        if word == 'title':
            score.title = rest
        elif word == 'tempo':
            score.tempo = float(rest)
        elif word == 'time':
            num, den = map(int, rest.split('/'))
            score.time_signature = (num, den)
            score.beats_per_measure = Fraction(4 * num, den)
        elif word == 'swing':
            score.swing = float(rest)
        elif word == 'pedal':
            score.pedal_style = rest
        elif word == 'order':
            order = []
            for part in rest.split():
                a, _, b = part.partition('-')
                order += range(int(a), int(b or a) + 1)
        elif word == 'bar':
            current = bars.setdefault(int(rest), {'chords': [], 'dyn': [], 'hairpin': [], 'fermata': []})
        elif current is None:
            raise ValueError(f'line {number}: "{word}" before the first bar')
        elif word in ('R', 'L'):
            current[word] = rest
        elif word == 'section':
            current['section'] = rest
        elif word in ('chords', 'dyn'):
            current[word] += [_at(item) for item in rest.split()]
        elif word == 'hairpin':
            sign, start, length = rest.split()
            current['hairpin'].append((int(sign), Fraction(start), Fraction(length)))
        elif word == 'fermata':
            current['fermata'].append(Fraction(rest))
        else:
            raise ValueError(f'line {number}: unknown "{word}"')

    length = score.beats_per_measure
    t, chord = Fraction(0), 0
    for index, bar in enumerate(order or sorted(bars)):
        if bar not in bars:
            raise ValueError(f'bar {bar} is in the order but not written')
        b = bars[bar]
        score.measure_starts.append(t)
        for staff, hand in ((0, 'R'), (1, 'L')):
            line, seen = b.get(hand, f'r:{length}'), {bar}
            while line.startswith('='):  # "= 5": same as bar 5
                ref = int(line[1:])
                if ref in seen:
                    raise ValueError(f'bar {bar} {hand}: copies itself')
                seen.add(ref)
                line = bars[ref].get(hand, f'r:{length}')
            pos = Fraction(0)
            for token in line.split():
                m = TOKEN.fullmatch(token)
                if not m:
                    raise ValueError(f'bar {bar} {hand}: cannot read "{token}"')
                dur = Fraction(m[2])
                if m[1] != 'r':
                    chord += 1
                    for name in m[1].split('+'):
                        p = pitch(name)
                        score.notes.append(Note(t + pos, dur, p, staff, index, True, chord, p,
                                                tie_next='~' in m[3], artic=m[3].replace('~', '')))
                pos += dur
            if pos != length:
                score.warnings.append(f'bar {bar} {hand}: adds up to {pos} beats, not {length}')
        for sym, at in b['chords']:
            score.harmony.append((t + at, sym))
        for level, at in b['dyn']:
            score.dynamics.append((t + at, level))
        for sign, start, span in b['hairpin']:
            score.hairpins.append((t + start, t + start + span, sign))
        for at in b['fermata']:
            score.fermatas.append((t + at, t + length))
        if 'section' in b:
            score.sections.append((t, b['section']))
        t += length
    merge_ties(score)
    for lst in (score.dynamics, score.harmony, score.sections, score.hairpins):
        lst.sort()
    return score
