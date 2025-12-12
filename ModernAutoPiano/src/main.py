import sys
import os
import threading
from pynput import keyboard
from midi_parser import parse_midi, load_mapping
from player import AutoPianoPlayer

# Configurations
if getattr(sys, 'frozen', False):
    # PyInstaller mode: sys.executable is the exe path
    # We assume the config folder is placed next to the exe or bundled.
    # If bundled with --add-data, it's in sys._MEIPASS
    # Let's assume we want config EXTERNAL for easy editing, so next to Executable.
    BASE_DIR = os.path.dirname(sys.executable)
    # If we are in 'dist/ModernAutoPiano', BASE_DIR is that dir.
else:
    # Normal python mode
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# MIDI_DIR: ../Midi relative to BASE_DIR
MIDI_DIR = os.path.join(os.path.dirname(BASE_DIR), "Midi")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "mappings.json")

def list_midi_files(directory):
    if not os.path.exists(directory):
        return []
    return [f for f in os.listdir(directory) if f.lower().endswith(('.mid', '.midi'))]

def generate_scale_events(mapping_str):
    events = []
    print("Generating scale test...")
    for char in mapping_str:
        # Press
        events.append((0.2, 'down', char))
        # Release
        events.append((0.1, 'up', char))
    return events

def main():
    print("=== Modern AutoPiano ===")
    print(f"MIDI Directory: {MIDI_DIR}")
    
    files = list_midi_files(MIDI_DIR)
    
    print("\nAvailable MIDI files:")
    print("0. [TEST] Play Full Keyboard Scale")
    for i, f in enumerate(files):
        print(f"{i + 1}. {f}")
    
    try:
        selection = input("\nSelect a file number to play (or 0 to test): ")
        if selection.strip() == '0':
            mapping_str = load_mapping(CONFIG_PATH)
            events = generate_scale_events(mapping_str)
            print(f"Loaded scale test with {len(events)} events.")
        else:
            idx = int(selection) - 1
            if 0 <= idx < len(files):
                selected_file = files[idx]
                full_path = os.path.join(MIDI_DIR, selected_file)
                print(f"\nLoading {selected_file}...")
                mapping = load_mapping(CONFIG_PATH)
                events = parse_midi(full_path, mapping)
                print(f"Loaded {len(events)} note events.")
            else:
                print("Invalid selection.")
                return
    except ValueError:
        print("Invalid input.")
        return
    except Exception as e:
        print(f"Error loading: {e}")
        return

    player = AutoPianoPlayer()
    
    print("\nControls:")
    print("  [DELETE] : Toggle Play/Pause")
    print("  [ESC]    : Quit")
    print("\nWaiting for input...")

    # Global listener
    def on_press(key):
        try:
            if key == keyboard.Key.delete:
                print("\n[Toggle Playback]")
                player.toggle(events)
            elif key == keyboard.Key.esc:
                print("\n[Quitting]")
                player.stop()
                return False # Stop listener
        except AttributeError:
            pass

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
    
    player.stop()
    print("Exited.")

if __name__ == "__main__":
    main()
