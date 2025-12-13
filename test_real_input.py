import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), 'ModernAutoPiano/src'))

print("Importing input_sim...")
try:
    import input_sim
    print("Import successful.")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

print("Attempting to press 'a' key in 3 seconds...")
time.sleep(3)
print("Pressing 'a'...")

try:
    print("Calling press_key('a')...")
    input_sim.press_key('a')
    print("Calling release_key('a')...")
    input_sim.release_key('a')
    print("Input sequence complete.")
except Exception as e:
    print(f"CRASH: {e}")

print("Test finished.")
