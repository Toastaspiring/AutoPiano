import sys
import os
import time
import threading
from pynput import keyboard

sys.path.append(os.path.join(os.path.dirname(__file__), 'ModernAutoPiano/src'))
import input_sim

stop_signal = False

def playback_thread():
    print("Thread: Starting...")
    for i in range(5):
        if stop_signal: break
        print(f"Thread: Pressing 'a' ({i})")
        input_sim.press_key('a')
        time.sleep(0.1)
        input_sim.release_key('a')
        time.sleep(0.5)
    print("Thread: Finished.")

def on_press(key):
    global stop_signal
    if key == keyboard.Key.esc:
        stop_signal = True
        return False

print("Main: Starting Listener...")
listener = keyboard.Listener(on_press=on_press)
listener.start()

print("Main: Starting Playback Thread...")
t = threading.Thread(target=playback_thread)
t.start()

print("Main: Joining Thread...")
t.join()
print("Main: Thread joined. Stopping Listener...")
listener.stop()
print("Main: Done.")
