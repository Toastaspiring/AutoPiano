import time
import threading
from pynput import keyboard
from input_sim import press_key, release_key

class AutoPianoPlayer:
    def __init__(self):
        self.is_playing = False
        self.stop_signal = False
        self._thread = None
        self.current_index = 0

    def play(self, events):
        """
        events: list of (wait_time_seconds, action, char_to_press)
        action: 'down' or 'up'
        """
        self.stop_signal = False
        self.is_playing = True
        # Restart from 0 if we finished previously, otherwise resume
        if self.current_index >= len(events):
            self.current_index = 0
            
        self._thread = threading.Thread(target=self._play_loop, args=(events,))
        self._thread.start()

    def _play_loop(self, events):
        print(f"Starting playback from event {self.current_index}...")
        
        # Iterate manually using range to track index
        for i in range(self.current_index, len(events)):
            if self.stop_signal:
                print("\n[Paused]")
                return # Thread ends, state preserved in self.current_index
            
            self.current_index = i
            wait_time, action, char = events[i]
            
            if wait_time > 0:
                time.sleep(wait_time)
            
            if action == 'down':
                press_key(char)
                print(f"v{char}", end=' ', flush=True)
            elif action == 'up':
                release_key(char)
                print(f"^{char}", end=' ', flush=True)
        
        self.is_playing = False
        self.current_index = 0 # Reset
        print("\nPlayback finished.")

    def stop(self):
        self.stop_signal = True
        if self._thread:
            self._thread.join()
        self.is_playing = False

    def toggle(self, events):
        if self.is_playing:
            self.stop()
        else:
            self.play(events)
