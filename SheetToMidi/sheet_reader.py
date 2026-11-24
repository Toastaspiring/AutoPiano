"""
Reads a MuseScore PDF export back into notes.

MuseScore draws every music symbol as a character of its music font (SMuFL code
points: Leland or Bravura in MuseScore 4, Emmentaler, named "MScore", in
MuseScore 3), and stems, beams, ties and staff lines as vector paths. So
instead of guessing from pixels like OMR software does, the score can be read
exactly: pitch from where a notehead sits on its staff, rhythm from its head,
beams, flags, dots and tuplets, and timing from how events line up in a measure.

Only grand-staff (piano) scores are handled: staves are read in pairs.
"""
import re
from dataclasses import dataclass, field
from fractions import Fraction

import pymupdf

# SMuFL code points
HEADS = {0xE0A2: Fraction(4), 0xE0A3: Fraction(2), 0xE0A4: Fraction(1)}
RESTS = {0xE4E3: Fraction(4), 0xE4E4: Fraction(2), 0xE4E5: Fraction(1), 0xE4E6: Fraction(1, 2),
         0xE4E7: Fraction(1, 4), 0xE4E8: Fraction(1, 8), 0xE4E9: Fraction(1, 16)}
FLAGS = {0xE240: 1, 0xE241: 1, 0xE242: 2, 0xE243: 2, 0xE244: 3, 0xE245: 3, 0xE246: 4, 0xE247: 4}
ACCIDENTALS = {0xE260: -1, 0xE261: 0, 0xE262: 1, 0xE263: 2, 0xE264: -2}
DOT = 0xE1E7
# Diatonic index (octave * 7 + step) of the line a clef glyph's origin sits on
CLEFS = {0xE050: 4 * 7 + 4, 0xE052: 3 * 7 + 4, 0xE053: 5 * 7 + 4,  # G4 line, 8vb, 8va
         0xE062: 3 * 7 + 3, 0xE064: 2 * 7 + 3,                     # F3 line, 8vb
         0xE05C: 4 * 7 + 0}                                        # C4 line
TIME_DIGITS = {0xE080 + i: i for i in range(10)}
DYNAMICS = {0xE52A: 'ppp', 0xE52B: 'pp', 0xE520: 'p', 0xE52C: 'mp', 0xE52D: 'mf',
            0xE522: 'f', 0xE52F: 'ff', 0xE530: 'fff'}
DYNAMIC_LETTERS = {0xE520: 'p', 0xE521: 'm', 0xE522: 'f'}  # MuseScore 3 spells "mf" letter by letter
ARTICULATIONS = {0xE4A0: '>', 0xE4A1: '>', 0xE4A2: "'", 0xE4A3: "'", 0xE4A6: "'", 0xE4A7: "'",
                 0xE4AC: '^', 0xE4AD: '^'}  # above / below the note
OTTAVAS = {0xE510: 12, 0xE514: 24, 0xE517: 36}  # the "8", "15", "22" of 8va/8vb lines
PEDAL_DOWN = 0xE650
TUPLET_RATIOS = {2: Fraction(3, 2), 3: Fraction(2, 3), 5: Fraction(4, 5), 6: Fraction(4, 6), 7: Fraction(4, 7)}

STEP_SEMITONES = [0, 2, 4, 5, 7, 9, 11]


def diatonic_to_midi(d, alter):
    return 12 * (d // 7 + 1) + STEP_SEMITONES[d % 7] + alter


@dataclass
class Glyph:
    code: int
    x: float
    y: float
    x1: float
    size: float


@dataclass
class Staff:
    top: float
    bottom: float
    x0: float
    x1: float

    @property
    def sp(self):
        return (self.bottom - self.top) / 4

    def distance(self, y):
        return max(self.top - y, 0, y - self.bottom)


@dataclass
class Event:
    """A chord or a rest, as printed."""
    staff: int
    x: float          # left edge of the column it is printed in
    base: Fraction    # undotted, untupleted length in quarter notes
    heads: list = field(default_factory=list)  # Glyphs, top to bottom; empty for a rest
    up: bool = True
    stem_x: float = None
    glyph: Glyph = None  # the rest symbol
    dots: int = 0
    artic: str = ''
    tuplet: Fraction = Fraction(1)
    onset: Fraction = None  # quarter notes from the start of its measure

    @property
    def duration(self):
        return self.base * (2 - Fraction(1, 2 ** self.dots)) * self.tuplet

    @property
    def is_rest(self):
        return not self.heads


@dataclass
class Note:
    start: Fraction  # quarter notes from the start of the piece
    duration: Fraction
    pitch: int
    staff: int        # 0 = upper staff (right hand), 1 = lower staff (left hand)
    measure: int      # 0-based
    up: bool          # stem direction, tells apart voices sharing a staff
    chord: int        # notes on one stem share this id
    diatonic: int = 0
    tie_next: bool = False
    artic: str = ''   # "'" staccato, '>' accent, '^' marcato


@dataclass
class Score:
    title: str = ''
    tempo: float = 100.0
    tempo_changes: list = field(default_factory=list)  # (time, bpm) after the start, if any
    time_signature: tuple = (4, 4)
    beats_per_measure: Fraction = Fraction(4)
    measure_starts: list = field(default_factory=list)  # quarter notes
    notes: list = field(default_factory=list)
    dynamics: list = field(default_factory=list)  # (time, 'mf')
    hairpins: list = field(default_factory=list)  # (start, end, +1 cresc / -1 dim)
    harmony: list = field(default_factory=list)   # (time, 'Bm7')
    lyrics: list = field(default_factory=list)    # times a sung syllable starts
    sections: list = field(default_factory=list)  # (time, 'CHORUS')
    pedal: list = field(default_factory=list)     # (start, end) of printed Ped. brackets
    pedal_sim: list = field(default_factory=list)  # times of "sim." (keep pedalling that way)
    pedal_style: str = 'auto'  # 'none' for music played without sustain pedal
    swing: float = 0.0  # where a swung offbeat eighth falls in the beat (0.5-0.67), 0 = straight
    fermatas: list = field(default_factory=list)  # (start, end) of held notes
    systems: list = field(default_factory=list)   # index of the first measure of each system
    warnings: list = field(default_factory=list)

    @property
    def end(self):
        return self.measure_starts[-1] + self.beats_per_measure if self.measure_starts else Fraction(0)


def _near(a, b, tol):
    return abs(a - b) <= tol


class _Page:
    """Everything printed on one page, sorted by kind."""

    def __init__(self, page):
        self.glyphs = []  # music font characters
        self.text = []    # (font, size, char, x, y, right edge)
        for tr in page.get_texttrace():
            font = tr['font'].split('+')[-1]
            music = any(f in font for f in ('Leland', 'Bravura', 'MScore')) and 'Text' not in font
            for ch in tr['chars']:
                (x, y), bbox = ch[2], ch[3]
                if music:
                    self.glyphs.append(Glyph(ch[0], x, y, bbox[2], tr['size']))
                else:
                    self.text.append((tr['font'], tr['size'], chr(ch[0]), x, y, bbox[2]))

        self.hlines, self.vlines, self.beams, self.curves, self.paths = [], [], [], [], []
        self.dashes = []  # dashed horizontal lines (8va), (x0, x1, y)
        self.slants = []  # lone slanted lines: MuseScore 3 hairpins, (ax, ay, bx, by)
        for d in page.get_drawings():
            items = d['items']
            width = d.get('width') or 0
            if d['type'] == 's' and len(items) == 1 and items[0][0] == 'l':
                a, b = items[0][1], items[0][2]
                if d.get('dashes') not in (None, '[] 0'):
                    if abs(a.y - b.y) < 0.01:
                        self.dashes.append((min(a.x, b.x), max(a.x, b.x), a.y))
                elif abs(a.y - b.y) < 0.01:
                    self.hlines.append((min(a.x, b.x), max(a.x, b.x), a.y, width))
                elif abs(a.x - b.x) < 0.01:
                    self.vlines.append((a.x, min(a.y, b.y), max(a.y, b.y), width))
                else:
                    self.slants.append((a.x, a.y, b.x, b.y))
            elif d['type'] == 's' and len(items) == 5 and all(i[0] == 'l' and abs(i[1].y - i[2].y) < 0.01 for i in items):
                # MuseScore 3 draws a staff's five lines as one path
                for _, a, b in items:
                    self.hlines.append((min(a.x, b.x), max(a.x, b.x), a.y, width))
            elif d['type'] == 'f' and len(items) == 4 and all(i[0] == 'l' for i in items):
                # Beam: a filled parallelogram; keep its centre line
                pts = [i[1] for i in items]
                x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
                left = [p.y for p in pts if p.x - x0 < 0.5]
                right = [p.y for p in pts if x1 - p.x < 0.5]
                if x1 - x0 > 1 and left and right:
                    self.beams.append((x0, x1, sum(left) / len(left), sum(right) / len(right)))
            elif (d['type'] == 'fs' and items and items[0][0] == 'c'
                  or d['type'] == 'f' and len(items) == 2 and all(i[0] == 'c' for i in items)):
                # Tie or slur: a filled crescent; keep its two tips
                p0, p1 = items[0][1], items[0][4]
                if p0.x > p1.x:
                    p0, p1 = p1, p0
                self.curves.append(((p0.x, p0.y), (p1.x, p1.y)))
            elif d['type'] == 's' and len(items) == 2 and all(i[0] == 'l' for i in items):
                # Hairpins, tuplet brackets, pedal brackets
                self.paths.append((width, [(i[1].x, i[1].y, i[2].x, i[2].y) for i in items]))


def _find_staves(page):
    """Groups of five evenly spaced horizontal lines covering the same span."""
    by_span = {}
    for x0, x1, y, w in page.hlines:
        if x1 - x0 > 30:
            by_span.setdefault((round(x0), round(x1)), []).append(y)
    found = {}
    for (x0, x1), ys in by_span.items():
        ys = sorted(set(round(y, 2) for y in ys))
        i = 0
        while i + 4 < len(ys):
            run = ys[i:i + 5]
            gaps = [b - a for a, b in zip(run, run[1:])]
            if 3 < gaps[0] < 8 and max(gaps) - min(gaps) < 0.3:
                s = found.get(round(run[0]))
                if s:
                    s.x0, s.x1 = min(s.x0, x0), max(s.x1, x1)
                else:
                    found[round(run[0])] = Staff(run[0], run[4], x0, x1)
                i += 5
            else:
                i += 1
    return sorted(found.values(), key=lambda s: s.top)


def read_pdf(path):
    doc = pymupdf.open(path)
    score = Score(title=(doc.metadata or {}).get('title') or '')
    reader = _Reader(score)
    for page in doc:
        p = _Page(page)
        staves = _find_staves(page=p)
        if len(staves) % 2:
            score.warnings.append(f'page {page.number + 1}: {len(staves)} staves, expected pairs')
        pairs = [(staves[i], staves[i + 1]) for i in range(0, len(staves) - 1, 2)]
        if not score.notes and score.tempo == 100.0:
            m = re.search(r'=\s*(\d+(?:\.\d+)?)', ''.join(t[2] for t in p.text))
            if m:
                score.tempo = float(m.group(1))
        for i, (upper, lower) in enumerate(pairs):
            # A system owns everything up to halfway to its neighbours
            top = (pairs[i - 1][1].bottom + upper.top) / 2 if i else upper.top - 90
            bottom = (lower.bottom + pairs[i + 1][0].top) / 2 if i + 1 < len(pairs) else lower.bottom + 90
            reader.read_system(p, upper, lower, top, bottom)
    reader.finish()
    return score


class _Reader:
    def __init__(self, score):
        self.score = score
        self.clef = [None, None]  # carried over from the previous system
        self.key = [{}, {}]       # diatonic step (0-6) -> alteration
        self.measure = 0
        self.chord_id = 0

    def read_system(self, p, upper, lower, sys_top, sys_bottom):
        staves = [upper, lower]
        sp = upper.sp
        x0, x1 = min(upper.x0, lower.x0), max(upper.x1, lower.x1)

        def staff_of(y):
            return 0 if upper.distance(y) <= lower.distance(y) else 1

        glyphs = [g for g in p.glyphs if sys_top < g.y < sys_bottom and x0 - 5 < g.x < x1 + 5]
        heads = [g for g in glyphs if g.code in HEADS and g.size > 12]  # skips grace/cue notes
        # Stems are thinner than barlines: 0.43 vs 0.77 in MuseScore 4, 0.65 vs 0.8 in MuseScore 3
        stems = [v for v in p.vlines if v[3] < 0.72 and v[2] - v[1] > 2 * sp - 1
                 and x0 < v[0] < x1 and sys_top < v[1] and v[2] < sys_bottom]
        bars = sorted(v[0] for v in p.vlines if v[3] >= 0.72 and x0 + 2 < v[0] < x1 + 1
                      and v[2] - v[1] > 3 * sp and sys_top < v[1] and v[2] < sys_bottom)
        beams = [b for b in p.beams if x0 < b[0] < x1 and sys_top < (b[2] + b[3]) / 2 < sys_bottom]

        clefs = [sorted((g for g in glyphs if g.code in CLEFS and staff_of(g.y) == s), key=lambda g: g.x)
                 for s in (0, 1)]

        def diatonic(g, s):
            clef = self.clef[s]
            for c in clefs[s]:
                if c.x < g.x:
                    clef = c
            return CLEFS[clef.code] + round((clef.y - g.y) / (staves[s].sp / 2))

        events = self._chords(heads, stems, beams, glyphs, staff_of, sp)
        events += [Event(staff_of(g.y), g.x, RESTS[g.code], glyph=g) for g in glyphs if g.code in RESTS]
        self._dots(events, glyphs, sp)
        self._tuplets(p, events, staves, beams, x0, x1, sys_top, sys_bottom)
        self._articulations(events, glyphs, staff_of, sp)
        ottavas = self._ottavas(p, glyphs, staves, staff_of, x0, x1, sys_top, sys_bottom)

        # The key signature is the run of accidentals straight after the clef that
        # starts the system; every other accidental belongs to the head to its right
        first_x = [min((e.x for e in events if e.staff == s), default=x1) for s in (0, 1)]
        accidentals = sorted((g for g in glyphs if g.code in ACCIDENTALS), key=lambda g: g.x)
        in_key = set()
        for s in (0, 1):
            start_clefs = [c for c in clefs[s] if c.x < first_x[s]]
            if not start_clefs:
                if self.clef[s] is None:
                    raise ValueError('no clef found at the start of the score')
                continue
            self.clef[s] = start_clefs[-1]
            key, edge = {}, start_clefs[-1].x1
            for g in accidentals:
                if staff_of(g.y) == s and edge - 0.5 < g.x < edge + 1.5 * sp:
                    key[diatonic(g, s) % 7] = ACCIDENTALS[g.code]
                    in_key.add(id(g))
                    edge = g.x1
            # Every system restates the key; none printed means no sharps or flats
            self.key[s] = key
        for g in accidentals:
            if id(g) in in_key:
                continue
            s = staff_of(g.y)
            cands = [h for e in events if e.staff == s for h in e.heads if abs(h.y - g.y) < 0.6 and 0 < h.x - g.x < 30]
            if cands:
                min(cands, key=lambda h: h.x - g.x).alter = ACCIDENTALS[g.code]
        digits = [g for g in glyphs if g.code in TIME_DIGITS and staff_of(g.y) == 0]
        if digits:
            rows = sorted({round(g.y) for g in digits})
            row = lambda y: int(''.join(str(TIME_DIGITS[g.code]) for g in sorted(digits, key=lambda g: g.x) if round(g.y) == y))
            self.score.time_signature = (row(rows[0]), row(rows[-1]))
            self.score.beats_per_measure = Fraction(4 * row(rows[0]), row(rows[-1]))
        length = self.score.beats_per_measure

        # Measures lie between barlines (a double barline counts once)
        edges = [x0]
        for b in bars:
            if b - edges[-1] < 5 and len(edges) > 1:
                edges[-1] = b
            elif b - edges[-1] >= 5:
                edges.append(b)
        if x1 - edges[-1] > 10:
            edges.append(x1)

        self.columns = []  # (x0, x1, start, length, [(x, onset)]) per measure of this system
        self.score.systems.append(self.measure)
        self.melody_cols = []  # (centre x, time) of upper-staff chords, to hang lyrics on
        for mx0, mx1 in zip(edges, edges[1:]):
            ev = sorted((e for e in events if mx0 <= e.x < mx1), key=lambda e: e.x)
            start = self.score.measure_starts[-1] + length if self.score.measure_starts else Fraction(0)
            self.score.measure_starts.append(start)
            for e in ev:
                if e.is_rest and e.base == 4 and not any(o.staff == e.staff and o is not e for o in ev):
                    e.base = length  # whole-measure rest
            self._time_measure(ev, length)
            self.columns.append((mx0, mx1, start, length, sorted((e.x, e.onset) for e in ev)))
            self.melody_cols += [((e.x + e.heads[0].x1) / 2, start + e.onset) for e in ev if e.staff == 0 and e.heads]
            self._emit(ev, start, diatonic, ottavas)
            self.measure += 1

        self._ties(p, events, sp, x1)
        self._markings(p, staves, staff_of, glyphs, x0, x1, sys_top, sys_bottom)
        for s in (0, 1):
            if clefs[s]:
                self.clef[s] = clefs[s][-1]

    # ---- reading symbols -----------------------------------------------------
    def _chords(self, heads, stems, beams, glyphs, staff_of, sp):
        events, used = [], set()
        for sx, ytop, ybot, _ in sorted(stems):
            mine = [h for h in heads if id(h) not in used and ytop - 1 <= h.y <= ybot + 1
                    and (_near(h.x, sx, 0.8) or _near(h.x1, sx, 0.8))]
            if not mine:
                continue
            hy = [h.y for h in mine]
            if max(hy) >= ybot - 2.5:
                up, far = True, ytop
            elif min(hy) <= ytop + 2.5:
                up, far = False, ybot
            else:
                continue
            used.update(id(h) for h in mine)
            # Heads on the usual side of the stem give the column; seconds sit on the other side
            normal = [h for h in mine if _near(h.x1 if up else h.x, sx, 0.8)] or mine
            base = HEADS[mine[0].code]
            if all(h.code == 0xE0A4 for h in mine):
                n = 0
                for bx0, bx1, by0, by1 in beams:
                    if bx0 - 0.6 <= sx <= bx1 + 0.6:
                        by = by0 + (sx - bx0) / (bx1 - bx0) * (by1 - by0)
                        if up and far - 1.2 * sp <= by <= far + 4 * sp and by < min(hy) - sp:
                            n += 1
                        elif not up and far - 4 * sp <= by <= far + 1.2 * sp and by > max(hy) + sp:
                            n += 1
                for g in glyphs:
                    if g.code in FLAGS and _near(g.x, sx, 1.0) and _near(g.y, far, 3 * sp):
                        n = max(n, FLAGS[g.code])
                base = Fraction(1, 2 ** n)
            events.append(Event(staff_of(sum(hy) / len(hy)), min(h.x for h in normal), base,
                                sorted(mine, key=lambda h: h.y), up, sx))
        # Stemless heads (whole notes) in one column make a chord
        stemless = []
        for h in sorted((h for h in heads if id(h) not in used), key=lambda h: h.x):
            s = staff_of(h.y)
            e = next((e for e in stemless if e.staff == s and _near(e.x, h.x, 1.5)), None)
            if e:
                e.heads.append(h)
                e.heads.sort(key=lambda h: h.y)
            else:
                stemless.append(Event(s, h.x, HEADS[h.code], [h]))
                if h.code != 0xE0A2:
                    self.score.warnings.append(f'measure ~{self.measure + 1}: notehead without a stem')
        return events + stemless

    @staticmethod
    def _dots(events, glyphs, sp):
        """Augmentation dots sit just right of the rightmost head, level with one of them."""
        dots = [g for g in glyphs if g.code == DOT]
        for e in events:
            if e.is_rest:
                right, ys, reach = e.glyph.x1, [e.glyph.y], 3 * sp
            else:
                right, ys, reach = max(h.x1 for h in e.heads), [h.y for h in e.heads], 0.55 * sp
            cols = sorted({round(d.x, 1) for d in dots
                           if right + 0.2 < d.x < right + 8 and any(abs(d.y - y) <= reach for y in ys)})
            last = right
            for cx in cols:
                if cx - last < 6:
                    e.dots, last = e.dots + 1, cx

    def _tuplets(self, p, events, staves, beams, x0, x1, sys_top, sys_bottom):
        nums = sorted((t for t in p.text if 'Italic' in t[0] and t[2].isdigit() and x0 + 25 < t[3] < x1
                       and sys_top < t[4] < sys_bottom), key=lambda t: (round(t[4]), t[3]))
        groups = []
        for t in nums:
            if groups and _near(groups[-1][-1][4], t[4], 1) and t[3] - groups[-1][-1][5] < 1:
                groups[-1].append(t)
            else:
                groups.append([t])
        brackets = [segs for w, segs in p.paths if w < 0.45]
        staff_of = lambda y: 0 if staves[0].distance(y) <= staves[1].distance(y) else 1
        for g in groups:
            n = int(''.join(t[2] for t in g))
            ratio = TUPLET_RATIOS.get(n)
            if ratio is None:
                continue
            nx0, nx1, ny = g[0][3], g[-1][5], g[0][4] - 3
            left = right = None
            for segs in brackets:
                flat = [s for s in segs if abs(s[1] - s[3]) < 0.01]
                if not flat or abs(flat[0][1] - ny) > 6:
                    continue
                hx0, hx1 = sorted((flat[0][0], flat[0][2]))
                if 0 < nx0 - hx1 < 6:
                    left = hx0
                if 0 < hx0 - nx1 < 6:
                    right = hx1
            if left is not None and right is not None:
                s = staff_of(ny)
                members = [e for e in events if e.staff == s and left - 1 <= e.x + 2 <= right + 1]
            else:
                cx = (nx0 + nx1) / 2
                mid = lambda b: (b[2] + b[3]) / 2
                near = [b for b in beams if b[0] - 2 <= cx <= b[1] + 2 and abs(mid(b) - ny) < 4 * staves[0].sp]
                if not near:
                    self.score.warnings.append(f'measure ~{self.measure + 1}: tuplet {n} with no bracket or beam')
                    continue
                # The closest beam; of a stack of beams, the longest one spans the whole group
                closest = min(near, key=lambda b: abs(mid(b) - ny))
                b = max((b for b in near if abs(mid(b) - mid(closest)) < 2 * staves[0].sp), key=lambda b: b[1] - b[0])
                members = [e for e in events if not e.is_rest and b[0] - 0.8 <= e.stem_x <= b[1] + 0.8
                           and staff_of((b[2] + b[3]) / 2) == e.staff]
            for e in members:
                e.tuplet = ratio

    @staticmethod
    def _articulations(events, glyphs, staff_of, sp):
        """Staccato dots and accents sit centred over or under the chord they belong to."""
        chords = [e for e in events if not e.is_rest]
        for g in glyphs:
            if g.code not in ARTICULATIONS:
                continue
            cx, s = (g.x + g.x1) / 2, staff_of(g.y)

            def gap(e):
                return max(min(h.y for h in e.heads) - g.y, g.y - max(h.y for h in e.heads), 0)
            near = [e for e in chords if e.staff == s and min(h.x for h in e.heads) - 0.5 < cx < max(h.x1 for h in e.heads) + 0.5
                    and gap(e) < 4.5 * sp]
            if near:
                e = min(near, key=gap)
                if ARTICULATIONS[g.code] not in e.artic:
                    e.artic += ARTICULATIONS[g.code]

    def _ottavas(self, p, glyphs, staves, staff_of, x0, x1, sys_top, sys_bottom):
        """8va / 8vb lines: (staff, x from, x to, semitones). The number starts a
        dashed line that runs, with a hook at its end, over the notes it moves."""
        marks = [(g.code, g.x, g.x1, g.y) for g in glyphs if g.code in OTTAVAS]
        marks += [(ord(ch), x, xr, y) for font, size, ch, x, y, xr in p.text if ord(ch) in OTTAVAS]
        spans = []
        for code, gx, gx1, gy in marks:
            if not (sys_top < gy < sys_bottom and x0 - 5 < gx < x1):
                continue
            s = staff_of(gy)
            sp = staves[s].sp
            end = None
            for dx0, dx1, dy in sorted(p.dashes):
                if abs(dy - gy) < 2 * sp and gx < dx0 < (end if end is not None else gx1) + 2 * sp:
                    end = dx1
            if end is None:
                end = x1
                self.score.warnings.append(f'measure ~{self.measure + 1}: 8va with no line, taken to the end of the system')
            spans.append((s, gx - 1, end, OTTAVAS[code] * (1 if gy < staves[s].top else -1)))
        return spans

    # ---- timing --------------------------------------------------------------
    @staticmethod
    def _columns_to_onsets(ev, tol):
        """Events printed in one column start together; the next column starts
        when the earliest event still sounding ends."""
        cols = []
        for e in ev:
            if cols and e.x - cols[-1][0].x < tol:
                cols[-1].append(e)
            else:
                cols.append([e])
        t, ends = Fraction(0), []
        for i, col in enumerate(cols):
            if i:
                later = [x for x in ends if x > t]
                t = min(later) if later else t
            for e in col:
                e.onset = t
                ends.append(t + e.duration)
        return max(ends, default=Fraction(0))

    def _time_measure(self, ev, length):
        # Each staff on its own first: a triplet in one hand can't then pull the
        # other hand's notes, printed a hair away, onto its beat
        for s in (0, 1):
            mine = [e for e in ev if e.staff == s]
            if mine and self._columns_to_onsets(mine, 1.5) != length:
                # Try lining it up against the other staff's columns instead
                others = [(e, e.onset) for e in ev if e.staff != s]
                self._columns_to_onsets(ev, 2.2)
                for e, onset in others:
                    e.onset = onset
                end = max(e.onset + e.duration for e in mine)
                if end != length:
                    self.score.warnings.append(f'measure {self.measure + 1} staff {s + 1}: adds up to {end} beats, not {length}')

    def _emit(self, ev, start, diatonic, ottavas):
        written = [{}, {}]  # accidentals in force in this measure, per staff position
        for e in sorted(ev, key=lambda e: (e.onset, e.x)):
            if e.is_rest:
                continue
            self.chord_id += 1
            for h in e.heads:
                d = diatonic(h, e.staff)
                if hasattr(h, 'alter'):
                    written[e.staff][d] = h.alter
                alter = written[e.staff].get(d, self.key[e.staff].get(d % 7, 0))
                shift = sum(n for s, a, b, n in ottavas if s == e.staff and a < h.x < b)
                h.note = Note(start + e.onset, e.duration, diatonic_to_midi(d, alter) + shift, e.staff,
                              self.measure, e.up, self.chord_id, d + shift // 12 * 7, artic=e.artic)
                self.score.notes.append(h.note)

    def _ties(self, p, events, sp, x1):
        """A tie is a flat curve from just right of a head to just before the
        next head on the same line (or off the end of the system)."""
        heads = [h for e in events for h in e.heads if hasattr(h, 'note')]
        system_end = self.score.measure_starts[-1] + self.score.beats_per_measure
        for (ax, ay), (bx, by) in p.curves:
            if abs(ay - by) > 0.4 * sp:
                continue
            starts = [h for h in heads if 0 < ax - h.x < 2.5 * sp and abs(ay - h.y) < 1.1 * sp]
            pairs = [(a, b) for a in starts for b in heads
                     if b.note.diatonic == a.note.diatonic and b.note.staff == a.note.staff
                     and b.note.start == a.note.start + a.note.duration and b.x - 1.5 * sp < bx < b.x1 + 0.5]
            if pairs:
                a, _ = min(pairs, key=lambda ab: abs(ay - ab[0].y) + (ab[1].x - bx) / 10)
                a.note.tie_next = True
            elif bx > x1 - 3 * sp:
                ends = [a for a in starts if a.note.start + a.note.duration == system_end]
                if ends:
                    min(ends, key=lambda a: abs(ay - a.y)).note.tie_next = True

    # ---- markings ------------------------------------------------------------
    def _time_at(self, x, snap=False):
        """Time of a horizontal position in the current system."""
        row = next((r for r in self.columns if x < r[1]), self.columns[-1])
        mx0, mx1, start, length, cols = row
        if not cols:
            return start
        if snap:
            return start + min(cols, key=lambda c: abs(c[0] - x))[1]
        if x <= cols[0][0]:
            return start
        pts = cols + [(mx1, length)]
        for (xa, ta), (xb, tb) in zip(pts, pts[1:]):
            if x <= xb:
                t = float(ta) + (float(tb) - float(ta)) * ((x - xa) / (xb - xa) if xb > xa else 0)
                return start + Fraction(round(t * 16), 16)
        return start + length

    def _markings(self, p, staves, staff_of, glyphs, x0, x1, sys_top, sys_bottom):
        score = self.score
        for g in glyphs:
            if g.code in DYNAMICS:
                score.dynamics.append((self._time_at((g.x + g.x1) / 2, snap=True), DYNAMICS[g.code]))
        words = []  # MuseScore 3: dynamics as separate letters of its text font
        for font, size, ch, x, y, xr in sorted(p.text, key=lambda t: t[3]):
            if ord(ch) in DYNAMIC_LETTERS and sys_top < y < sys_bottom and x0 - 5 < x < x1:
                if words and abs(words[-1][3] - y) < 1 and x - words[-1][2] < 2:
                    words[-1][0] += DYNAMIC_LETTERS[ord(ch)]
                    words[-1][2] = xr
                else:
                    words.append([DYNAMIC_LETTERS[ord(ch)], x, xr, y])
        for text, x, xr, y in words:
            if text in DYNAMICS.values():
                score.dynamics.append((self._time_at((x + xr) / 2, snap=True), text))

        # Hairpins: both lines leave from the narrow end; on the left it opens up (cresc.)
        wedges = [segs for w, segs in p.paths if 0.48 < w < 0.6]
        slants = [(ax, ay, bx, by) if ax < bx else (bx, by, ax, ay) for ax, ay, bx, by in p.slants]
        for i, a in enumerate(slants):  # MuseScore 3: two loose lines meeting at one end
            for b in slants[i + 1:]:
                if _near(a[0], b[0], 0.5) and _near(a[2], b[2], 0.5):
                    if _near(a[1], b[1], 0.5):
                        wedges.append(((a[2], a[3], a[0], a[1]), b))
                    elif _near(a[3], b[3], 0.5):
                        wedges.append((a, b))
        for (ax, ay, bx, by), _ in wedges:
            if sys_top < ay < sys_bottom and x0 - 5 < min(ax, bx) < x1:
                lo, hi = sorted((ax, bx))
                score.hairpins.append((self._time_at(lo), self._time_at(hi), 1 if _near(bx, lo, 1) else -1))

        # Chord symbols (sans-serif) and boxed section labels (bold) above the upper staff
        words = []
        for font, size, ch, x, y, xr in sorted(p.text, key=lambda t: t[3]):
            if not (sys_top < y < staves[0].top) or not x0 - 5 < x < x1:
                continue
            kind = 'harmony' if 'Sans' in font else 'section' if 'Arial-Bold' in font and 9 < size < 13 else None
            if kind is None:
                continue
            w = next((w for w in words if w[0] == kind and abs(y - w[4]) < 4 and -1 < x - w[3] < 2), None)
            if w:
                w[1] += ch
                w[3] = xr
            else:
                words.append([kind, ch, x, xr, y])
        for kind, text, x, xr, y in words:
            text = text.strip()
            if kind == 'harmony' and text:
                score.harmony.append((self._time_at(x + 2, snap=True), text))
            elif kind == 'section' and text:
                score.sections.append((self._time_at((x + xr) / 2), text))

        # Lyrics between the staves: each syllable is sung on the upper-staff note above it
        syllables = []
        between = sorted((t for t in p.text if staves[0].bottom < t[4] < staves[1].top and x0 < t[3] < x1
                          and not any(k in t[0] for k in ('Italic', 'Bold', 'Sans'))), key=lambda t: (round(t[4]), t[3]))
        for font, size, ch, x, y, xr in between:
            last = syllables[-1] if syllables else None
            if ch in ' -_':
                if last:
                    last[3] = True  # closed
            elif last and not last[3] and abs(y - last[4]) < 2 and x - last[2] < 1:
                last[2] = xr
            else:
                syllables.append([ch, x, xr, False, y])
        for ch, x, xr, _, y in syllables:
            if ch.isalnum() and self.melody_cols:
                cx, onset = min(self.melody_cols, key=lambda c: abs(c[0] - (x + xr) / 2))
                if abs(cx - (x + xr) / 2) < 3 * staves[0].sp:
                    score.lyrics.append(onset)

        # Pedal: "Ped." starts a bracket that runs to its closing hook
        below = lambda y: y > staves[1].bottom
        peds = sorted(g.x for g in glyphs if g.code == PEDAL_DOWN and below(g.y))
        hooks = sorted(segs[-1][2] for w, segs in p.paths if 0.45 < w < 0.5 and below(segs[-1][1])
                       and sys_top < segs[-1][1] < sys_bottom and x0 - 5 < segs[-1][2] < x1 + 5)
        for px in peds:
            end = next((h for h in hooks if h > px), x1)
            score.pedal.append((self._time_at(px + 2, snap=True), self._time_at(end)))
        for font, size, ch, x, y, xr in p.text:
            if 'Italic' in font and ch == 's' and below(y) and sys_top < y < sys_bottom and x0 < x < x1:
                score.pedal_sim.append(self._time_at(x))

    def finish(self):
        score = self.score
        merge_ties(score)
        score.lyrics = sorted(set(score.lyrics))
        # No pedal marks but plenty of staccato: it is meant to be played dry
        if not score.pedal and not score.pedal_sim and sum("'" in n.artic for n in score.notes) > len(score.notes) / 10:
            score.pedal_style = 'none'
        for lst in (score.dynamics, score.harmony, score.sections, score.pedal, score.hairpins):
            lst.sort()


def merge_ties(score):
    """Tied notes become one long note."""
    by_line = {}
    for n in sorted(score.notes, key=lambda n: n.start):
        by_line.setdefault((n.staff, n.diatonic), []).append(n)
    merged = set()
    for seq in by_line.values():
        for i, n in enumerate(seq):
            if id(n) in merged:
                continue
            cur = n
            while cur.tie_next:
                nxt = next((m for m in seq[i + 1:] if m.start == n.start + n.duration and id(m) not in merged), None)
                if nxt is None:
                    score.warnings.append(f'measure {cur.measure + 1}: tie on pitch {n.pitch} leads to no note')
                    break
                n.duration += nxt.duration
                merged.add(id(nxt))
                cur = nxt
            n.tie_next = False
    score.notes = sorted((n for n in score.notes if id(n) not in merged), key=lambda n: (n.start, n.staff, n.pitch))
