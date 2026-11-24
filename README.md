# AutoPiano

Plays MIDI files on Roblox / Virtual Piano style pianos by simulating key presses.

```bash
cd ModernAutoPiano
pip install -r requirements.txt
python run.py
```

Put your songs in [Midi/](./Midi). If the app prints a TRANS value, set the in-game piano's TRANS to it so the song plays in its original key.

See [ModernAutoPiano/README.md](./ModernAutoPiano/README.md) for technical details.

## Making songs from sheet music

[SheetToMidi](./SheetToMidi) turns a MuseScore PDF into a MIDI that sounds played by a person (rubato, dynamics, pedal), and can humanize MIDI files you already have:

```bash
cd SheetToMidi
pip install -r requirements.txt
python run.py "path/to/sheet.pdf"
```

---
*Project maintained by Toastaspiring.*
