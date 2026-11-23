"""
Reads an existing (usually robotic) MIDI file into a Score so it can be humanized.

A MIDI file knows less than a sheet: there are no chord symbols, sections,
dynamics or pedal marks. The humanizer copes: phrases fall every four bars, the
pedal changes every bar and on bass notes, and loudness follows the file's own
velocities if they vary, or stays mezzo-forte if they don't.
"""
from fractions import Fraction
from statistics import mean, pstdev

import mido

from sheet_reader import Note, Score
from humanizer import LEVELS


def read_midi(path):
    mid = mido.MidiFile(path)
    ppq = mid.ticks_per_beat
    score = Score(title=str(path).replace('\\', '/').rsplit('/', 1)[-1].rsplit('.', 1)[0])
    tempos, sig = [], None
    tracks = []  # per track: [(start_tick, end_tick, pitch, velocity)]
    for track in mid.tracks:
        tick, open_notes, done = 0, {}, []
        for msg in track:
            tick += msg.time
            if msg.type == 'set_tempo':
                tempos.append((tick, mido.tempo2bpm(msg.tempo)))
            elif msg.type == 'time_signature' and sig is None:
                sig = (msg.numerator, msg.denominator)
            elif msg.type == 'note_on' and msg.velocity > 0:
                open_notes.setdefault((msg.channel, msg.note), []).append((tick, msg.velocity))
            elif msg.type in ('note_off', 'note_on'):
                stack = open_notes.get((msg.channel, msg.note))
                if stack:
                    start, vel = stack.pop(0)
                    if msg.channel != 9 and tick > start:  # skip drums
                        done.append((start, tick, msg.note, vel))
        if done:
            tracks.append(done)
    if not tracks:
        raise ValueError('no notes in this MIDI file')

    beat = lambda t: Fraction(t, ppq).limit_denominator(96)
    tempos.sort()
    score.tempo = tempos[0][1] if tempos else 120.0
    score.tempo_changes = [(beat(t), bpm) for t, bpm in tempos[1:]]
    score.time_signature = sig or (4, 4)
    score.beats_per_measure = Fraction(4 * score.time_signature[0], score.time_signature[1])

    # Two or more note tracks: the higher one is the right hand. One track: split at middle C.
    if len(tracks) >= 2:
        ranked = sorted(range(len(tracks)), key=lambda i: -mean(n[2] for n in tracks[i]))
        hand = {i: (0 if r == 0 else 1) for r, i in enumerate(ranked)} if len(tracks) == 2 else None
    else:
        hand = None
    raw = []
    for i, tr in enumerate(tracks):
        for start, end, pitch, vel in tr:
            staff = hand[i] if hand else (0 if pitch >= 60 else 1)
            raw.append((beat(start), beat(end) - beat(start), pitch, vel, staff))

    # Drop whole bars of silence at the start, keeping the notes on their beats
    bar = score.beats_per_measure
    first = int(min(r[0] for r in raw) / bar) * bar
    raw = [(s - first, d, p, v, st) for s, d, p, v, st in raw]
    end = max(s + d for s, d, *_ in raw)
    score.measure_starts = [bar * i for i in range(int(end / bar) + 1)]
    chords = {}
    for s, d, p, v, st in sorted(raw):
        cid = chords.setdefault((s, st), len(chords) + 1)
        score.notes.append(Note(s, d, p, st, int(s / bar), True, cid, 0))

    # Loudness: keep the file's dynamics, two bars at a time, if it has any
    vels = [r[3] for r in raw]
    if pstdev(vels) > 6:
        for m in range(0, len(score.measure_starts), 2):
            lo, hi = m * bar, (m + 2) * bar
            here = [r[3] for r in raw if lo <= r[0] < hi]
            if here:
                avg = mean(here)
                score.dynamics.append((lo, min(LEVELS, key=lambda k: abs(LEVELS[k] - avg))))
    return score
