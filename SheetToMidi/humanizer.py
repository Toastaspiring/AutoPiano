"""
Turns a Score into a MIDI performance that sounds played rather than sequenced.

What a pianist does that a sequencer doesn't, and what this copies:
- Tempo breathes: phrases push forward a little in the middle and relax at the
  end, sections take a breath before they start, the last bars slow down.
- Hands are never perfectly together: every chord lands a few milliseconds off
  the grid, the melody note a touch before the rest.
- The melody sings over the accompaniment, downbeats lean, offbeats are lighter,
  phrases swell and fade, and printed dynamics and hairpins are followed.
- Legato: melody notes overlap slightly, accompaniment lets go a little early.
- The sustain pedal is changed just after each new harmony (legato pedalling),
  with a real pedal's travel instead of an on/off switch.

Notes struck together stay within CHORD_SPREAD of each other, so AutoPiano
still sends them as one chord (its window is 10 ms).
"""
import bisect
import math
import random
import re
from dataclasses import dataclass
from fractions import Fraction

import mido

CHORD_SPREAD = 0.008  # seconds; AutoPiano groups notes within 10 ms into one chord
PLAYER_WINDOW = 0.0105  # that 10 ms, plus a tick of rounding
LEVELS = {'ppp': 30, 'pp': 40, 'p': 50, 'mp': 62, 'mf': 74, 'f': 88, 'ff': 100, 'fff': 112}
SECTION_TEMPO = {'CHORUS': 1.015, 'BRIDGE': 0.97, 'OUTRO': 0.95}
PPQ = 960


@dataclass
class Style:
    seed: int = None
    timing: float = 1.0    # scales every timing deviation
    dynamics: float = 1.0  # scales every loudness deviation
    pedal: bool = True
    chord_spread: float = CHORD_SPREAD


@dataclass
class Played:
    on: float
    off: float
    pitch: int
    velocity: int
    hand: int


# ---- harmony -------------------------------------------------------------------
ROOTS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def chord_tones(symbol):
    """Pitch classes of a chord symbol like 'F#m7', 'C♯m7♭5' or 'G6'."""
    symbol = symbol.replace('♯', '#').replace('♭', 'b')
    m = re.match(r'([A-G])([#b]?)([^/]*)(?:/([A-G][#b]?))?', symbol)
    if not m:
        return None
    root = (ROOTS[m[1]] + {'#': 1, 'b': -1, '': 0}[m[2]]) % 12
    q = m[3]
    minor = q.startswith('m') and not q.startswith('maj') or 'dim' in q
    third = 5 if 'sus4' in q else 2 if 'sus2' in q else 3 if minor else 4
    fifth = 6 if 'b5' in q or 'dim' in q else 8 if 'aug' in q or '+' in q or '#5' in q else 7
    tones = {0, third, fifth}
    if 'maj' in q:
        tones.add(11)
    elif 'dim7' in q:
        tones.add(9)
    elif any(d in q for d in ('7', '9', '11', '13')):
        tones.add(10)
    if '6' in q:
        tones.add(9)
    if '9' in q:
        tones.add(2)
    if '11' in q:
        tones.add(5)
    pcs = {(root + t) % 12 for t in tones}
    if m[4]:
        pcs.add((ROOTS[m[4][0]] + (1 if '#' in m[4] else -1 if 'b' in m[4] else 0)) % 12)
    return pcs


# ---- helpers -------------------------------------------------------------------
def _smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _ar_noise(n, rho, sigma, rng):
    """Correlated noise: drifts instead of jumping around."""
    out, v = [], 0.0
    k = math.sqrt(1 - rho * rho)
    for _ in range(n):
        v = rho * v + rng.gauss(0, sigma) * k
        out.append(v)
    return out


class Performer:
    def __init__(self, score, style=None):
        self.score = score
        self.style = style or Style()
        self.rng = random.Random(self.style.seed)
        self.end = float(score.end)
        self.measures = [float(m) for m in score.measure_starts]
        self.bar = float(score.beats_per_measure)
        self._phrases()
        self._tempo_map()

    # ---- structure ----------------------------------------------------------
    def _snap_to_bar(self, t):
        return min(self.measures, key=lambda m: abs(m - float(t)))

    def _phrases(self):
        """Sections from the score's labels, cut into 4-bar phrases (2-bar halves)."""
        starts = sorted({self._snap_to_bar(t) for t, _ in self.score.sections} | {0.0})
        names = {self._snap_to_bar(t): name.split()[0] for t, name in self.score.sections}
        self.sections = [(a, b, names.get(a, '')) for a, b in zip(starts, starts[1:] + [self.end])]
        self.phrases = []
        for a, b, _ in self.sections:
            t = a
            while t < b - 1e-9:
                length = min(4 * self.bar, b - t)
                if b - (t + length) < 2 * self.bar - 1e-9 and b - (t + length) > 1e-9:
                    length = b - t  # don't leave a stub shorter than two bars
                self.phrases.append((t, t + length))
                t += length

    def _section_at(self, t):
        return next((s for s in self.sections if s[0] <= t < s[1]), self.sections[-1])

    def _phrase_at(self, t):
        return next((p for p in self.phrases if p[0] <= t < p[1]), self.phrases[-1])

    # ---- tempo ----------------------------------------------------------------
    def _tempo_factor(self, b, drift):
        r = self.style.timing
        f = 1.0
        # Section character, blended in over a beat so it never jumps
        a, e, name = self._section_at(b)
        here = SECTION_TEMPO.get(name, 1.0)
        prev = self._section_at(a - 0.01)[2] if a > 0 else name
        f *= 1 + (SECTION_TEMPO.get(prev, 1.0) + (here - SECTION_TEMPO.get(prev, 1.0)) * _smooth(b - a) - 1) * r
        # Phrase arch: move on in the middle, relax into the end
        p0, p1 = self._phrase_at(b)
        pos = (b - p0) / (p1 - p0)
        f *= 1 + 0.018 * r * math.sin(math.pi * pos)
        last_beat = _smooth(b - (p1 - 1.0))
        is_section_end = any(abs(p1 - s[1]) < 1e-6 for s in self.sections)
        f *= 1 - (0.11 if is_section_end else 0.045) * r * last_beat
        # Hairpins push a little
        for h0, h1, sign in self.score.hairpins:
            if float(h0) <= b < float(h1) and sign > 0:
                f *= 1 + 0.02 * r
        # Final ritardando over the last bar and a half
        f *= 1 - 0.38 * r * _smooth((b - (self.end - 1.5 * self.bar)) / (1.5 * self.bar)) ** 1.4
        return f * (1 + drift * r)

    def _tempo_map(self):
        step = 1 / 32
        n = int(self.end / step) + 64
        beat_noise = _ar_noise(int(self.end) + 4, 0.85, 0.012, self.rng)

        def drift(b):
            i = int(b)
            w = 0.5 - 0.5 * math.cos(math.pi * (b - i))
            return beat_noise[i] * (1 - w) + beat_noise[i + 1] * w

        self.grid = [0.0]
        for i in range(n):
            b = i * step
            bpm = self._base_tempo(b) * self._tempo_factor(b + step / 2, drift(b + step / 2))
            self.grid.append(self.grid[-1] + 60.0 / bpm * step)
        self.step = step

    def _base_tempo(self, b):
        bpm = self.score.tempo
        for at, value in self.score.tempo_changes:
            if float(at) <= b:
                bpm = value
        return bpm

    def time(self, beat):
        """Seconds at a score position, following the breathing tempo."""
        x = float(beat) / self.step
        i = min(int(x), len(self.grid) - 2)
        return self.grid[i] + (self.grid[i + 1] - self.grid[i]) * (x - i)

    # ---- who plays what ---------------------------------------------------------
    def _melody(self, notes):
        """Top line of the right hand. Where there are lyrics, notes with a
        syllable are the tune and others only continue it if they stay close;
        elsewhere, figures that drop well below the tune are accompaniment."""
        rh = [n for n in notes if n.staff == 0]
        onsets = {}
        for n in rh:
            onsets.setdefault(n.start, []).append(n)
        sung = sorted(self.score.lyrics)
        melody, level, held, last_off = set(), None, None, None
        for t in sorted(onsets):
            group = onsets[t]
            if last_off is not None and t - last_off >= 1:
                level = None  # after a rest the tune can start anywhere
            top = max(group, key=lambda n: n.pitch)
            i = bisect.bisect_left(sung, t)
            near_lyrics = (i < len(sung) and sung[i] - t <= 2) or (i > 0 and t - sung[i - 1] <= 4)
            if held and held.start + held.duration > t and top.pitch < held.pitch - 2:
                pass  # inner voice moving under a held melody note
            elif i < len(sung) and sung[i] == t:
                melody.add(id(top))
                held, level = top, top.pitch
                last_off = max([last_off or 0] + [n.start + n.duration for n in group])
                continue
            elif near_lyrics and held and top.pitch < held.pitch - 4:
                pass  # chords under a sung note
            elif level is not None and top.pitch < level - 7:
                pass  # accompaniment figure
            else:
                melody.add(id(top))
                held = top
                level = top.pitch if level is None else 0.7 * level + 0.3 * top.pitch
            last_off = max([last_off or 0] + [n.start + n.duration for n in group])
        return melody

    # ---- loudness -----------------------------------------------------------------
    def _level(self, t):
        level = LEVELS['mf'] if not self.score.dynamics else LEVELS.get(self.score.dynamics[0][1], 74)
        marks = [(float(a), LEVELS.get(d, 74)) for a, d in self.score.dynamics]
        for a, v in marks:
            if a <= t + 1e-9:
                level = v
        for h0, h1, sign in self.score.hairpins:
            h0, h1 = float(h0), float(h1)
            if t < h0:
                continue
            before = next((v for a, v in reversed(marks) if a <= h0 + 1e-9), level)
            target = next((v for a, v in marks if h1 - 0.5 <= a <= h1 + self.bar), None)
            if target is None or (target - before) * sign <= 0:
                target = before + 12 * sign
            if t <= h1:
                level = before + (target - before) * (t - h0) / max(h1 - h0, 1e-6)
            elif not any(h1 < a <= t for a, _ in marks):
                level = target
        return level

    def _metric(self, t):
        pos = (t - self._snap_down(t)) % self.bar
        if abs(pos) < 1e-6:
            return 4
        if abs(pos - self.bar / 2) < 1e-6 and self.bar >= 4:
            return 2
        if abs(pos - round(pos)) < 1e-6:
            return 0
        if abs(pos * 2 - round(pos * 2)) < 1e-6:
            return -3
        return -5

    def _snap_down(self, t):
        return max((m for m in self.measures if m <= t + 1e-9), default=0.0)

    # ---- the performance -----------------------------------------------------------
    def perform(self):
        score, rng, st = self.score, self.rng, self.style
        notes = score.notes
        melody = self._melody(notes)
        melody_notes = sorted((n for n in notes if id(n) in melody), key=lambda n: n.start)

        # The peak of each phrase's tune gets a tiny hesitation before it
        peaks = set()
        for p0, p1 in self.phrases:
            inside = [n for n in melody_notes if p0 <= n.start < p1]
            if inside:
                peaks.add(max(inside, key=lambda n: (n.pitch, -n.start)).start)
        medians = {}
        for p in self.phrases:
            pitches = sorted(n.pitch for n in melody_notes if p[0] <= n.start < p[1])
            medians[p] = pitches[len(pitches) // 2] if pitches else 72

        onsets = sorted({n.start for n in notes})
        jitter = dict(zip(onsets, _ar_noise(len(onsets), 0.4, 0.008 * st.timing, rng)))
        force = dict(zip(onsets, _ar_noise(len(onsets), 0.5, 2.0 * st.dynamics, rng)))

        by_onset = {}
        for n in notes:
            by_onset.setdefault(n.start, []).append(n)
        played, chord_times = [], []
        for t in onsets:
            group = by_onset[t]
            ft = float(t)
            base_time = self.time(t) + jitter[t]
            if t in peaks:
                base_time += 0.015 * st.timing
            # Spread within the chord: melody first, then the rest, hands slightly apart
            offs = []
            for n in group:
                o = rng.gauss(0, 0.002) + (0.003 if n.staff == 1 else 0.0)
                if id(n) in melody:
                    o -= 0.004
                offs.append(o)
            lo, hi = min(offs), max(offs)
            if hi - lo > st.chord_spread:
                offs = [lo + (o - lo) * st.chord_spread / (hi - lo) for o in offs]
            lo = min(offs)
            chord_times.append(base_time)

            # Phrase swell: grows to about two thirds of the way, then fades
            p = self._phrase_at(ft)
            pos = (ft - p[0]) / (p[1] - p[0])
            arch = -1 + 5 * _smooth(pos / 0.65) if pos < 0.65 else 4 - 7 * _smooth((pos - 0.65) / 0.35)
            level = self._level(ft)
            lowest_lh = min((n.pitch for n in group if n.staff == 1), default=None)
            for n, o in zip(group, offs):
                v = level + st.dynamics * (arch + self._metric(ft)) + force[t]
                if id(n) in melody:
                    v += 7 * st.dynamics + max(-5, min(5, 0.3 * (n.pitch - medians[p]))) * st.dynamics
                elif n.staff == 0:
                    v -= 9 * st.dynamics
                elif n.pitch == lowest_lh:
                    v -= 5 * st.dynamics
                else:
                    v -= 11 * st.dynamics
                if n.duration > Fraction(1, 2):
                    v += min(4.0, 2 * math.log2(float(n.duration) / 0.5)) * st.dynamics
                v += rng.gauss(0, 3) * st.dynamics
                on = base_time + o - lo
                end = self.time(n.start + n.duration)
                length = end - on
                if id(n) in melody:
                    off = end + rng.gauss(0.022, 0.008) * st.timing  # legato overlap
                elif n.staff == 0:
                    off = end - max(0.015, 0.08 * length) + rng.gauss(0, 0.006) * st.timing
                else:
                    off = end - rng.gauss(0.02, 0.008) * st.timing
                if n.duration <= Fraction(1, 4):
                    off = min(off, on + max(0.8 * length, 0.05))
                played.append(Played(on, max(off, on + 0.04), n.pitch, int(max(12, min(118, round(v)))), n.staff))

        # The same key can't be held twice: release before it is struck again
        played.sort(key=lambda p: (p.pitch, p.on))
        keep = []
        for p in played:
            prev = keep[-1] if keep and keep[-1].pitch == p.pitch else None
            if prev and p.on - prev.on < 0.012:
                prev.velocity, prev.off = max(prev.velocity, p.velocity), max(prev.off, p.off)
                continue  # both hands on one key: one strike
            if prev and prev.off > p.on - 0.02:
                prev.off = max(prev.on + 0.02, p.on - 0.02)
            keep.append(p)
        # AutoPiano strikes everything within 10 ms of a group's first event as one
        # chord, so a key let go just before a chord would split it: let go just after
        chord_times.sort()
        for p in keep:
            i = bisect.bisect_right(chord_times, p.off)
            if i < len(chord_times) and chord_times[i] - p.off < PLAYER_WINDOW:
                p.off = chord_times[i] + 0.0005
        played = sorted(keep, key=lambda p: p.on)

        pedal = self._pedal(notes) if st.pedal else []
        return played, pedal

    # ---- sustain pedal -------------------------------------------------------------
    def _pedal(self, notes):
        """Pedal changes as (time in beats, kind): 'change' lifts just after the
        new notes and goes back down, 'up' lifts, 'down' presses."""
        score = self.score
        printed = [(float(a), float(b)) for a, b in score.pedal]
        sims = sorted(float(t) for t in score.pedal_sim)
        # Brackets followed by "sim." start a stretch pedalled by ear; it lasts until
        # the next printed bracket that isn't itself the start of another sim.
        auto = []
        for s in sims:
            start = max((a for a, _ in printed if a <= s + 0.01), default=s)
            nxt = [a for a, _ in printed if a > s + 1 and not any(a <= x <= a + 1 for x in sims)]
            auto.append((start, min(nxt) if nxt else self.end))
        if not printed:
            auto = [(0.0, self.end)]

        events = []
        for a, b in printed:
            if any(x0 <= a < x1 for x0, x1 in auto):
                continue
            events.append((a, 'change'))
            if not any(abs(c - b) < 0.5 for c, _ in printed if c > a) and not any(abs(x0 - b) < 0.5 for x0, _ in auto):
                events.append((b, 'up'))
        harmony = [(float(t), chord_tones(h)) for t, h in score.harmony]
        for x0, x1 in auto:
            points = {x0} | {m for m in self.measures if x0 <= m < x1} | {t for t, _ in harmony if x0 <= t < x1}
            # A bass note outside the chord gets its own pedal, and so does the next one
            bass = {}
            for n in notes:
                if n.staff == 1 and x0 <= n.start < x1:
                    t = float(n.start)
                    if t not in bass or n.pitch < bass[t].pitch:
                        bass[t] = n
            outside = False
            for t in sorted(bass):
                n = bass[t]
                tones = next((tn for ht, tn in reversed(harmony) if ht <= t + 1e-9), None)
                if tones is None or n.duration < Fraction(1, 2):
                    continue
                now_outside = n.pitch % 12 not in tones
                if now_outside or outside:
                    points.add(t)
                outside = now_outside
            events += [(t, 'change') for t in points]
            if x1 < self.end and not any(abs(a - x1) < 0.5 for a, _ in printed):
                events.append((x1, 'up'))
        events.sort()
        # Keep the pedal down to the end, then let the last chord ring out
        out = []
        last_change = -1
        for t, kind in events:
            if kind == 'change' and t - last_change < 0.24:
                continue
            out.append((t, kind))
            if kind == 'change':
                last_change = t
        return out

    def pedal_messages(self, pedal, last_off):
        """CC64 values over time, with the pedal's travel instead of a switch."""
        rng = self.rng
        msgs = []
        down = False

        def press(t):
            depth = rng.randint(108, 127)
            for i, v in enumerate((28, 64, 96, depth)):
                msgs.append((t + i * 0.012, v))

        def lift(t):
            for i, v in enumerate((90, 52, 18, 0)):
                msgs.append((t + i * 0.008, v))

        for beat, kind in pedal:
            t = self.time(beat)
            if kind == 'change':
                if down:
                    lift(t + rng.uniform(0.015, 0.035) * self.style.timing)
                press(t + rng.uniform(0.09, 0.14))
                down = True
            elif kind == 'up' and down:
                lift(t - 0.01)
                down = False
        if down:
            lift(last_off + 0.6)
        msgs.sort()
        return msgs


def plain(score):
    """The score exactly as written: no pedal, no feel. Useful for checking notes."""
    p = Performer(score, Style(timing=0, dynamics=0, pedal=False))
    played = [Played(p.time(n.start), p.time(n.start + n.duration) - 0.01, n.pitch, 80, n.staff)
              for n in score.notes]
    return sorted(played, key=lambda p: p.on), []


def write_midi(path, score, played, pedal_msgs, lead_in=0.25):
    mid = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    tempo = mido.bpm2tempo(score.tempo)
    to_ticks = lambda s: int(round((s + lead_in) * 1e6 / tempo * PPQ))

    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage('track_name', name=score.title or 'Piano', time=0))
    meta.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
    meta.append(mido.MetaMessage('time_signature', numerator=score.time_signature[0],
                                 denominator=score.time_signature[1], time=0))
    mid.tracks.append(meta)

    def track(name, events):
        tr = mido.MidiTrack()
        tr.append(mido.MetaMessage('track_name', name=name, time=0))
        tr.append(mido.Message('program_change', program=0, channel=0, time=0))
        now = 0
        for tick, order, msg in sorted(events, key=lambda e: (e[0], e[1])):
            tr.append(msg.copy(time=tick - now))
            now = tick
        mid.tracks.append(tr)

    for hand, name in ((0, 'Right Hand'), (1, 'Left Hand')):
        ev = []
        for p in played:
            if p.hand == hand:
                ev.append((to_ticks(p.on), 1, mido.Message('note_on', note=p.pitch, velocity=p.velocity)))
                ev.append((to_ticks(p.off), 0, mido.Message('note_off', note=p.pitch, velocity=0)))
        track(name, ev)
    if pedal_msgs:
        track('Sustain Pedal', [(to_ticks(t), 0, mido.Message('control_change', control=64, value=v))
                                for t, v in pedal_msgs])
    mid.save(path)
    return mid
