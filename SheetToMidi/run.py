"""
Make a MIDI file that sounds like a person playing it.

    python run.py sheet.pdf             # MuseScore PDF -> Midi/<name>.mid
    python run.py song.mid              # robotic MIDI  -> <name> (humanized).mid
    python run.py sheet.pdf --plain     # exact notes, no feel (to check the reading)
"""
import argparse
import sys
from pathlib import Path

from humanizer import Performer, Style, plain, write_midi

MIDI_DIR = Path(__file__).resolve().parent.parent / 'Midi'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', help='a MuseScore PDF, or a MIDI file to humanize')
    ap.add_argument('-o', '--output', help='where to write the MIDI file')
    ap.add_argument('--seed', type=int, help='same seed, same performance (default: a new one each run)')
    ap.add_argument('--timing', type=float, default=1.0, help='how loose the timing is (0 = metronome, 1 = default)')
    ap.add_argument('--dynamics', type=float, default=1.0, help='how much loudness varies (0 = flat, 1 = default)')
    ap.add_argument('--no-pedal', action='store_true', help='leave out the sustain pedal')
    ap.add_argument('--tempo', type=float, help='override the tempo (BPM)')
    ap.add_argument('--plain', action='store_true', help='write the notes exactly as written, no humanizing')
    args = ap.parse_args()

    src = Path(args.input)
    if src.suffix.lower() == '.pdf':
        from sheet_reader import read_pdf
        score = read_pdf(src)
        out = Path(args.output) if args.output else MIDI_DIR / f'{src.stem}{" (plain)" if args.plain else ""}.mid'
    elif src.suffix.lower() in ('.mid', '.midi'):
        from midi_reader import read_midi
        score = read_midi(src)
        out = Path(args.output) if args.output else src.with_name(f'{src.stem} ({"plain" if args.plain else "humanized"}).mid')
    else:
        sys.exit('Give a .pdf exported from MuseScore or a .mid file.')
    if args.tempo:
        scale = args.tempo / score.tempo
        score.tempo = args.tempo
        score.tempo_changes = [(t, bpm * scale) for t, bpm in score.tempo_changes]

    for w in score.warnings:
        print(f'[!] {w}')
    if args.plain:
        played, pedal_msgs = plain(score)
    else:
        performer = Performer(score, Style(seed=args.seed, timing=args.timing, dynamics=args.dynamics,
                                           pedal=not args.no_pedal))
        played, pedal = performer.perform()
        pedal_msgs = performer.pedal_messages(pedal, max(p.off for p in played)) if pedal else []
    out.parent.mkdir(parents=True, exist_ok=True)
    write_midi(out, score, played, pedal_msgs)

    length = max(p.off for p in played)
    print(f'{score.title or src.stem}: {len(score.measure_starts)} bars, {len(played)} notes, '
          f'{score.tempo:g} BPM, {int(length // 60)}:{int(length % 60):02d}')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
