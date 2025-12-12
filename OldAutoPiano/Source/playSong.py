from pynput import keyboard
import os
import time
import ctypes
from ctypes import wintypes
import mido

# Set the path to the MIDI folder
midi_folder = './midi_files'

stopPumping = False
user32 = ctypes.WinDLL('user32', use_last_error=True)
tstart = time.time()
isPlaying = False

# Define the keyboard input functions
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

class KEYBDINPUT(ctypes.Structure):
    _fields_ = (("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", wintypes.ULONG_PTR))

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = (("ki", KEYBDINPUT),)
    _anonymous_ = ("_input",)
    _fields_ = (("type", wintypes.DWORD), ("_input", _INPUT))

LPINPUT = ctypes.POINTER(INPUT)

def PressKey(hexKeyCode):
    x = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=hexKeyCode))
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

def ReleaseKey(hexKeyCode):
    x = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=hexKeyCode, dwFlags=KEYEVENTF_KEYUP))
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

def isShifted(charIn):
    return charIn.isupper() or charIn in "!@#$%^&*()"

def getKeyValue(charIn):
    return ord(charIn)

def pressLetter(charIn):
    kv = getKeyValue(charIn)
    if isShifted(charIn):
        PressKey(160)  # Shift
        PressKey(kv)
        ReleaseKey(kv)
        ReleaseKey(160)  # Release Shift
    else:
        PressKey(kv)
        ReleaseKey(kv)

def loadMidiFile(midi_file_path):
    midi = mido.MidiFile(midi_file_path)
    tempo = 500000  # Default tempo (in microseconds per beat)
    notes = []

    for msg in midi:
        if msg.type == 'set_tempo':
            tempo = msg.tempo
        elif msg.type == 'note_on' and msg.velocity > 0:
            note = msg.note
            if 21 <= note <= 108:  # C1 to C7
                char = keyboard_mapping[note - 21]  # Adjust index based on mapping
                time_in_seconds = mido.tick2second(msg.time, midi.ticks_per_beat, tempo / 1_000_000)
                notes.append((time_in_seconds, char))

    return tempo, notes

# Your custom keyboard layout
keyboard_mapping = "1!2@34$5%6^78*9(0qQwWeErtTyYuiIoOpPasSdDfgGhHjJklLzZxcCvVbBnm"

def runMidiPlayback(midi_file):
    global isPlaying
    isPlaying = True
    tempo, notes = loadMidiFile(midi_file)
    tstart = time.time()

    for wait_time, note in notes:
        if not isPlaying:
            break
        time.sleep(wait_time)  # Wait for the correct time
        print(f"Playing note: {note}")
        pressLetter(note)

# Keyboard Listener
def on_press(key):
    global isPlaying
    try:
        if key.char == 'delete':
            isPlaying = not isPlaying
            if isPlaying:
                runMidiPlayback(midi_file_path)
    except AttributeError:
        pass

# Ask for the MIDI file in the specified folder
midi_file_path = input("Enter the name of the MIDI file (in 'midi_files' folder): ")
midi_file_path = os.path.join(midi_folder, midi_file_path)

# Start the keyboard listener
listener = keyboard.Listener(on_press=on_press)
listener.start()

# Keep the script running
listener.join()
