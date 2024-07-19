# MIDI Processing and Playback

## Overview

This project consists of two main Python scripts, `playSong.py` and `pyMIDI.py`. Together, they provide functionality to process MIDI files and play them back using keyboard automation.

## Files

### `playSong.py`

This script is responsible for monitoring keyboard events and playing back MIDI sequences through simulated keyboard inputs. It uses the `ctypes` library for low-level keyboard event handling and `pyHook` for capturing keypresses.

#### Key Features:
- **Keyboard Event Handling**: Uses `ctypes` to simulate keyboard inputs and control playback.
- **Key Event Listener**: Monitors for a specific key (Delete) to toggle the playback state.
- **MIDI Playback**: Simulates key presses to play MIDI notes as per the processed sequence.

### `pyMIDI.py`

This script processes MIDI files, extracting note information and formatting it for playback by `playSong.py`. It reads MIDI files, sorts notes, removes duplicates, and formats the data into a text file that can be used for playback.

#### Key Features:
- **MIDI File Reading**: Reads and parses MIDI files to extract note information.
- **Note Sorting**: Sorts and processes notes to combine simultaneous notes and remove duplicates.
- **Output Formatting**: Creates a text file with the formatted note sequences for use by `playSong.py`.

## Dependencies

- `pyHook`: For capturing keyboard events.
- `pythoncom`: For handling COM objects required by `pyHook`.
- `ctypes`: For low-level input simulation.

## Usage

### Setting Up

1. **Install Dependencies**:
   ```bash
   pip install pyHook pythoncom
   ```

2. **Prepare MIDI Files**:
   - Place your MIDI files in a designated directory (e.g., `C:\\Users\\your_username\\Documents\\AutoPiano\\Midi`).

### Running the Scripts

1. **Process a MIDI File**:
   - Run `pyMIDI.py` to process a MIDI file.
   - Follow the prompts to select a MIDI file and generate the formatted output.

   ```bash
   python pyMIDI.py
   ```

2. **Play the Processed MIDI**:
   - Run `playSong.py` to start the playback script.
   - Use the Delete key to toggle playback on and off.

   ```bash
   python playSong.py
   ```

## Script Details

### `playSong.py`

```python
import sys
import os
import time
import ctypes
from ctypes import wintypes
import pyHook
import pythoncom

# Global variables
stopPumping = False
user32 = ctypes.WinDLL('user32', use_last_error=True)
tstart = time.time()
isPlaying = False

def OnKeyDown(event):
    global isPlaying
    if event.Key == "Delete":
        isPlaying = not isPlaying
        if isPlaying:
            runMacro()
    return True

# Define input structures and constants
# (Keyboard and Mouse input handling omitted for brevity)

# Playback function
def runMacro():
    # Load song.txt and simulate key presses
    # (Implementation omitted for brevity)

# Hook manager setup
hm = pyHook.HookManager()
hm.KeyDown = OnKeyDown
hm.HookKeyboard()
pythoncom.PumpMessages()
```

### `pyMIDI.py`

```python
import os

class MidiFile:
    def __init__(self, file_path):
        self.file_path = file_path
        self.tempo = 120  # Default tempo
        self.notes = []
        self.midiSong = open("song.txt", "w")
        self.midiSheet = open("sheet.txt", "w")
        self.process_midi()

    def process_midi(self):
        # Read and parse the MIDI file
        # Extract notes and write to song.txt
        # (Implementation omitted for brevity)

# Main script execution
if __name__ == "__main__":
    path = "C:\\Users\\louis\\Documents\\AutoPiano\\Midi"
    fileList = os.listdir(path)
    midList = [f for f in fileList if f.endswith(".mid")]

    print("Press letter of midi file to process")
    for i, mid in enumerate(midList):
        print(chr(97 + i), ":", mid)

    choice = input().strip()
    midi = MidiFile(os.path.join(path, midList[ord(choice) - 97]))
```

## Notes

- Ensure your MIDI files are properly formatted and located in the specified directory.
- Modify paths and configurations as needed to match your system setup.

---

This README provides an overview of the functionality, setup instructions, and detailed descriptions of the scripts and their usage.
