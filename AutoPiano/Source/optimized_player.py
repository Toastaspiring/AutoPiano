import mido
import time
import argparse

# Conditional import for pynput
try:
    from pynput.keyboard import Controller
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

# A dictionary to map MIDI notes to keyboard keys.
# This range (36-81) covers a standard 61-key piano range, mapping C1-C6.
NOTE_TO_KEY = {
    36: 'q', 37: '2', 38: 'w', 39: '3', 40: 'e', 41: 'r', 42: '5',
    43: 't', 44: '6', 45: 'y', 46: '7', 47: 'u', 48: 'i', 49: '9',
    50: 'o', 51: '0', 52: 'p', 53: '[', 54: '=', 55: ']', 56: 'a',
    57: 'z', 58: 's', 59: 'x', 60: 'd', 61: 'c', 62: 'f', 63: 'v',
    64: 'g', 65: 'b', 66: 'h', 67: 'n', 68: 'j', 69: 'm', 70: 'k',
    71: ',', 72: 'l', 73: '.', 74: ';', 75: '/', 76: "'", 77: '\\',
    78: ' ', 79: ' ', 80: ' ', 81: ' ' # Using space for the highest notes for now
}


def play_midi(file_path, no_keyboard=False):
    """
    Plays a MIDI file by simulating keyboard presses.
    If no_keyboard is True, it will only print the actions.
    """
    keyboard = None
    if not no_keyboard:
        if PYNPUT_AVAILABLE:
            keyboard = Controller()
        else:
            print("Warning: pynput library not found or display not available. Running in test mode.")
            print("Keyboard simulation will be disabled.")
            no_keyboard = True

    try:
        midi_file = mido.MidiFile(file_path)
        print(f"Playing {file_path}. Press Ctrl+C to stop.")

        for msg in midi_file.play():
            if msg.type == 'note_on' and msg.velocity > 0:
                if msg.note in NOTE_TO_KEY:
                    key_to_action = NOTE_TO_KEY[msg.note]
                    print(f"Press: {key_to_action}")
                    if not no_keyboard and keyboard:
                        keyboard.press(key_to_action)
                else:
                    print(f"Note {msg.note} not in map.")

            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in NOTE_TO_KEY:
                    key_to_action = NOTE_TO_KEY[msg.note]
                    print(f"Release: {key_to_action}")
                    if not no_keyboard and keyboard:
                        keyboard.release(key_to_action)

    except KeyboardInterrupt:
        print("\nPlayback stopped by user.")
    except Exception as e:
        print(f"An error occurred during playback: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play a MIDI file by simulating keyboard presses.")
    parser.add_argument('midi_file', help='The path to the MIDI file to play.')
    parser.add_argument('--no-keyboard', action='store_true', help='Run in test mode without simulating keypresses.')
    args = parser.parse_args()

    if not args.no_keyboard:
        print("Starting player in 5 seconds... Switch to the target window now!")
        time.sleep(5)

    try:
        play_midi(args.midi_file, args.no_keyboard)
    except FileNotFoundError:
        print(f"Error: MIDI file not found at {args.midi_file}")

    print("Playback finished.")
