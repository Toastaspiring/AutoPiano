import time
import threading
from pynput import keyboard
from input_sim import press_keys, release_keys, release_all

# Notes this close together (seconds) are pressed as one chord
CHORD_WINDOW = 0.01

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
        try:
            # Wait times are deltas, but we schedule them against one clock so the
            # Shift delays inside press_keys don't push every later note back.
            target_time = time.perf_counter()
            i = self.current_index
            while i < len(events):
                self.current_index = i # Resume point if paused while waiting
                target_time += events[i][0]

                # Events landing within CHORD_WINDOW of the first are sent together
                j = i + 1
                spread = 0.0
                while j < len(events) and spread + events[j][0] <= CHORD_WINDOW:
                    spread += events[j][0]
                    j += 1

                # Sleep in small chunks to allow interrupting
                while not self.stop_signal:
                    remaining = target_time - time.perf_counter()
                    if remaining <= 0:
                        break
                    time.sleep(min(0.05, remaining))

                if self.stop_signal:
                    release_all() # Don't leave notes stuck down while paused
                    print("\n[Paused]")
                    return # Thread ends, state preserved in self.current_index

                releases, presses, late_releases = [], [], []
                for _, action, char in events[i:j]:
                    if action == 'down':
                        presses.append(char)
                    elif char in presses:
                        late_releases.append(char) # Zero-length note: release after pressing
                    else:
                        releases.append(char)

                print(f"[DEBUG] Evt {i}-{j - 1}: up={releases} down={presses}")
                release_keys(releases)
                press_keys(presses)
                release_keys(late_releases)

                target_time += spread
                i = j

            release_all() # In case the MIDI left a note without its note_off
            self.is_playing = False
            self.current_index = 0 # Reset
            print("\nPlayback finished.")
            
        except Exception as e:
            import traceback
            print(f"\n[ERROR] Playback crashed: {e}")
            traceback.print_exc()
            self.is_playing = False

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
