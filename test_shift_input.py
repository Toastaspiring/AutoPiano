import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), 'ModernAutoPiano/src'))
try:
    import input_sim
except ImportError:
    sys.exit(1)

print("Attempting to press 'Y' (Shift+y) in 2 seconds...")
time.sleep(2)
print("Pressing 'Y'...")
try:
    input_sim.press_key('Y')
    input_sim.release_key('Y')
    print("SUCCESS: 'Y' pressed.")
except Exception as e:
    print(f"CRASH: {e}")
