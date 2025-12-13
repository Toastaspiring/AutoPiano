import sys
import os
import threading
import msvcrt
from pynput import keyboard
from midi_parser import parse_midi, load_mapping, get_tracks_info
from player import AutoPianoPlayer

# Configurations
if getattr(sys, 'frozen', False):
    # PyInstaller mode: sys.executable is the exe path
    BASE_DIR = os.path.dirname(sys.executable)
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
        events.append((0.2, 'down', char))
        events.append((0.1, 'up', char))
    return events

def select_tracks_interactive(tracks):
    """
    Interactive console menu to select tracks.
    tracks: list of dicts {'name': str, 'is_drum': bool}
    Returns: list of selected indices (integers) or None if all/default.
    """
    # Smart Default: Select everything EXCEPT drums
    selected = set()
    for i, t in enumerate(tracks):
        if not t['is_drum']:
            selected.add(i)
            
    # Cursor 0 = Validate
    # Cursor 1..N = Tracks
    cursor = 0
    
    while True:
        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("--- Smart Track Selector ---")
        print("auto-selected 'Piano/Melodic' tracks. [Drums] are unselected.")
        print("Use UP/DOWN to move, ENTER to toggle.")
        print("-" * 30)
        
        # Option 0: Validate
        pointer = ">" if cursor == 0 else " "
        print(f"{pointer} [ VALIDATE / PLAY ]")
        
        print("-" * 30)

        for i, t in enumerate(tracks):
            mark = "[*]" if i in selected else "[ ]"
            pointer = ">" if (cursor - 1) == i else " "
            drum_tag = " [DRUMS]" if t['is_drum'] else ""
            print(f"{pointer} {mark} {t['name']}{drum_tag}")
            
        # Input handling
        key = msvcrt.getch()
        try:
            if key == b'\xe0': # Special key prefix
                key = msvcrt.getch()
                if key == b'H': # Up
                    cursor = max(0, cursor - 1)
                elif key == b'P': # Down
                    cursor = min(len(tracks), cursor + 1)
            elif key == b'\r': # Enter
                if cursor == 0:
                    return list(selected) if selected else None
                else:
                    track_idx = cursor - 1
                    if 0 <= track_idx < len(tracks):
                        if track_idx in selected:
                            selected.remove(track_idx)
                        else:
                            selected.add(track_idx)
        except:
             pass

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
                
                # Interactive Track Selection
                try:
                    tracks = get_tracks_info(full_path)
                    if len(tracks) > 1:
                        selected_indices = select_tracks_interactive(tracks)
                    else:
                        selected_indices = None
                except Exception as e:
                    print(f"Error reading tracks: {e}")
                    selected_indices = None

                mapping = load_mapping(CONFIG_PATH)
                events = parse_midi(full_path, mapping, selected_indices)
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
