import sys
import os
import time
import threading
from pynput import keyboard

sys.path.append(os.path.join(os.path.dirname(__file__), 'ModernAutoPiano/src'))
try:
    from player import AutoPianoPlayer
except ImportError:
    print("Failed to import player")
    sys.exit(1)

# Mock events that mimic BlueBossa start
# (0.0, 'down', 'h'), (0.0, 'down', 'Y')
events = [
    (0.0, 'down', 'h'),
    (0.0, 'down', 'Y'),
    (0.5, 'up', 'h'),
    (0.0, 'up', 'Y')
]

player = AutoPianoPlayer()

def on_press(key):
    try:
        if key == keyboard.Key.space: # Use space for test
            print("\n[Space] Triggering Toggle...")
            player.toggle(events)
        elif key == keyboard.Key.esc:
            print("\n[Esc] Quitting...")
            player.stop()
            return False
    except Exception as e:
        print(f"Error: {e}")

print("=== HANG REPRO SCRIPT ===")
print("Press SPACE to play. Press ESC to quit.")
print("Waiting...")

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()

print("Exited.")
