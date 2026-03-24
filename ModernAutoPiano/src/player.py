import time
import threading
from input_sim import press_key, release_key

class AutoPianoPlayer:
    def __init__(self, on_event=None):
        self.is_playing = False
        self.stop_signal = False
        self._thread = None
        self.current_index = 0
        self.on_event = on_event  # optional callback(action: str, char: str)
        self.practice_mode = False  # when True, skip key presses (learning mode)

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
        try:
            for i in range(self.current_index, len(events)):
                if self.stop_signal:
                    return

                self.current_index = i
                wait_time, action, char = events[i]

                if wait_time > 0:
                    end_time = time.time() + wait_time
                    while time.time() < end_time:
                        if self.stop_signal:
                            break
                        time.sleep(min(0.05, end_time - time.time()))

                if self.stop_signal:
                    return

                if not self.practice_mode:
                    if action == 'down':
                        press_key(char)
                    elif action == 'up':
                        release_key(char)

                if self.on_event:
                    self.on_event(action, char)

            self.is_playing = False
            self.current_index = 0

        except Exception as e:
            import traceback
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
