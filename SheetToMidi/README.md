# SheetToMidi

Turns piano sheet music into a MIDI file that sounds like someone playing it, not a sequencer.

```bash
cd SheetToMidi
pip install -r requirements.txt
python run.py "path/to/sheet.pdf"          # -> Midi/<sheet name>.mid
python run.py "../Midi/Some Song.mid"      # humanize a MIDI you already have
```

The result plays in AutoPiano like any other song, and in any MIDI player or DAW (velocity and sustain pedal included).

## Which sheets work

PDFs **exported from MuseScore** (musescore.com downloads included), for piano (two staves). MuseScore writes every note as a character of its music font, with stems, beams and ties as vector lines, so the score is read exactly: no image recognition and no guessed notes. Scanned or photographed sheets won't work.

It reads pitches, key signatures, accidentals, clefs (including mid-score changes), rhythm (beams, flags, dots, triplets, rests), ties, dynamics, hairpins, chord symbols, section labels, lyrics and pedal marks. Each bar is checked to add up to the time signature; anything that doesn't is printed as a warning.

## What makes it sound human

| | Robot | SheetToMidi |
|---|---|---|
| Tempo | Fixed | Phrases push forward in the middle and relax at the end, sections take a breath, the last bars slow down |
| Timing | On the grid | Every chord a few ms off, correlated so it drifts rather than jitters; melody note a touch early |
| Loudness | One velocity | Follows *p*, *mf*, *f* and hairpins; phrases swell and fade; downbeats lean, offbeats are lighter |
| Voicing | All equal | The melody sings over the chords (found from the lyrics where there are some), inner notes and bass sit under it |
| Note lengths | Exact | Melody overlaps slightly (legato), accompaniment lets go a little early |
| Pedal | None | Follows the printed *Ped.* marks; under *sim.* it changes on every bar, chord change and passing bass note, lifting just after the new notes like a pianist does |

Notes struck together stay within 8 ms of each other, so AutoPiano still sends them as one chord.

## Options

| Option | |
|---|---|
| `-o file.mid` | Where to save |
| `--seed 5` | Same seed, same performance. Without it, every run plays a little differently |
| `--timing 0.5` | Tighter timing (0 = metronome, 1 = default, 1.5 = looser) |
| `--dynamics 0.5` | Flatter loudness (0 = all the same) |
| `--tempo 80` | Different speed |
| `--no-pedal` | No sustain pedal |
| `--plain` | Exact notes, no humanizing: handy to check the sheet was read right |

## Files

```
SheetToMidi/
├── run.py           # command line
├── sheet_reader.py  # MuseScore PDF -> notes and markings
├── midi_reader.py   # existing MIDI -> notes
└── humanizer.py     # notes -> performance -> MIDI file
```
