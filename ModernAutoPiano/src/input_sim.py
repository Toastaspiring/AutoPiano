import ctypes
import time
from collections import Counter
from ctypes import wintypes

# Types
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

# Check if ULONG_PTR is defined in wintypes, otherwise define it
if not hasattr(wintypes, 'ULONG_PTR'):
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        wintypes.ULONG_PTR = ctypes.c_ulonglong
    else:
        wintypes.ULONG_PTR = ctypes.c_ulong

class KEYBDINPUT(ctypes.Structure):
    _fields_ = (("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", wintypes.ULONG_PTR))

class MOUSEINPUT(ctypes.Structure):
    _fields_ = (("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", wintypes.ULONG_PTR))

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD))

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = (("mi", MOUSEINPUT),
                    ("ki", KEYBDINPUT),
                    ("hi", HARDWAREINPUT))
    _anonymous_ = ("_input",)
    _fields_ = (("type", wintypes.DWORD), ("_input", _INPUT))

LPINPUT = ctypes.POINTER(INPUT)
user32 = ctypes.WinDLL('user32', use_last_error=True)

def _send_input(vk, scan, flags):
    x = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags))
    result = user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
    if result == 0:
        print(f"[InputErr] SendInput failed. Error: {ctypes.get_last_error()}")
    # else:
       # Print debug for success to verify Scan Code
       # print(f"[InputDebug] Sent vk={vk} scan={scan} flags={flags}")

def get_scan_code(vk):
    return user32.MapVirtualKeyW(vk, 0) # MAPVK_VK_TO_VSC = 0

# Hardcoded QWERTY Scan Codes to ensure layout independence
# Maps char -> (Scan Code, Needs Shift)
# scan codes are hex
QWERTY_MAP = {
    '1': (0x02, False), '!': (0x02, True),
    '2': (0x03, False), '@': (0x03, True),
    '3': (0x04, False), # '3' is just 3
    '4': (0x05, False), '$': (0x05, True),
    '5': (0x06, False), '%': (0x06, True),
    '6': (0x07, False), '^': (0x07, True),
    '7': (0x08, False), # '7' is just 7? Mappings say 7 and 8 have no shift alt usually? Wait.
    # Standard VP mapping: 1! 2@ 3 4$ 5% 6^ 7 8* 9( 0)
    # My mapping string: 1!2@34$5%6^78*9(0
    '8': (0x09, False), '*': (0x09, True),
    '9': (0x0A, False), '(': (0x0A, True),
    '0': (0x0B, False), # '0'
    
    # Letters
    'q': (0x10, False), 'Q': (0x10, True),
    'w': (0x11, False), 'W': (0x11, True),
    'e': (0x12, False), 'E': (0x12, True),
    'r': (0x13, False), 'R': (0x13, True),
    't': (0x14, False), 'T': (0x14, True),
    'y': (0x15, False), 'Y': (0x15, True),
    'u': (0x16, False), 'U': (0x16, True),
    'i': (0x17, False), 'I': (0x17, True),
    'o': (0x18, False), 'O': (0x18, True),
    'p': (0x19, False), 'P': (0x19, True),
    'a': (0x1E, False), 'A': (0x1E, True),
    's': (0x1F, False), 'S': (0x1F, True),
    'd': (0x20, False), 'D': (0x20, True),
    'f': (0x21, False), 'F': (0x21, True),
    'g': (0x22, False), 'G': (0x22, True),
    'h': (0x23, False), 'H': (0x23, True),
    'j': (0x24, False), 'J': (0x24, True),
    'k': (0x25, False), 'K': (0x25, True),
    'l': (0x26, False), 'L': (0x26, True),
    'z': (0x2C, False), 'Z': (0x2C, True),
    'x': (0x2D, False), 'X': (0x2D, True),
    'c': (0x2E, False), 'C': (0x2E, True),
    'v': (0x2F, False), 'V': (0x2F, True),
    'b': (0x30, False), 'B': (0x30, True),
    'n': (0x31, False), 'N': (0x31, True),
    'm': (0x32, False), 'M': (0x32, True),
}

def get_vk_info(char_in):
    # This function is legacy now, replaced by direct lookups in QWERTY_MAP
    # But kept for fallback if needed.
    res = user32.VkKeyScanW(ord(char_in))
    if res == -1:
        return ord(char_in.upper()), False
    return res & 0xFF, (res >> 8) & 1

SHIFT_VK = 0xA0 # VK_LSHIFT
SHIFT_SCAN = 0x2A # Scan Code for LShift

# The piano reads the Shift state some time after the key event arrives, and
# while a song is playing that lag reaches ~100ms. If Shift is already up by
# then, the black key plays as the white key under it; if Shift goes down too
# soon after a white key, the white key plays as the black one.
# Measured in Roblox Got Talent: 30ms gave 83 wrong notes in 30s of Take Five,
# 100ms gave none.
SHIFT_HOLD = 0.1 # seconds Shift stays down after the shifted keys go down
SHIFT_LEAD = 0.1 # seconds between the last plain key and Shift going down

# The game also misses a key that goes up and back down (or down and up) within
# the same frame, so each key keeps its state at least this long before changing.
KEY_GAP = 0.04 # seconds

_last_plain_press = 0.0

# Scan code -> number of notes currently holding that physical key.
# q/Q share one key, and so do re-struck or doubled notes in the MIDI.
_held = Counter()

# Scan code -> time that key last went down or up
_last_change = {}

def _wait_for_keys(scans):
    ready = max((_last_change.get(scan, 0.0) + KEY_GAP for scan in scans), default=0.0)
    remaining = ready - time.perf_counter()
    if remaining > 0:
        time.sleep(remaining)

def _send_key(vk, scan, up):
    _send_input(vk, scan, KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0))
    _last_change[scan] = time.perf_counter()

def _lookup(char_in):
    # Check manual map first (Force QWERTY)
    if char_in in QWERTY_MAP:
        scan, needs_shift = QWERTY_MAP[char_in]
        # For Scan Code injection, VK is ignored, usually pass 0
        return 0, scan, needs_shift
    # Fallback to system layout
    vk, needs_shift = get_vk_info(char_in)
    return vk, get_scan_code(vk), needs_shift

def press_keys(chars):
    """
    Presses several keys as one chord: plain keys first, then every shifted key
    under a single Shift hold so a chord only pays the Shift delay once.
    A key that is still held by an earlier note is lifted and pressed again so
    the game hears the new note; it stays down until its last note is released.
    """
    global _last_plain_press
    plain, shifted, retrigger, chord_scans = [], [], [], set()
    for char_in in chars:
        if not char_in: continue
        vk, scan, needs_shift = _lookup(char_in)
        _held[scan] += 1
        if scan in chord_scans:
            continue # Doubled note, or q and Q in one chord: the key only goes down once
        chord_scans.add(scan)
        if _held[scan] > 1:
            # A press on a key that is already down is ignored by the game
            retrigger.append((vk, scan))
        (shifted if needs_shift else plain).append((vk, scan))

    if retrigger:
        _wait_for_keys(scan for _, scan in retrigger)
        for vk, scan in retrigger:
            _send_key(vk, scan, up=True)
    _wait_for_keys(chord_scans)

    for vk, scan in plain:
        _send_key(vk, scan, up=False)
        _last_plain_press = time.perf_counter()

    if not shifted:
        return

    # Let the game read the plain keys without Shift before it goes down
    remaining = _last_plain_press + SHIFT_LEAD - time.perf_counter()
    if remaining > 0:
        time.sleep(remaining)

    _send_input(SHIFT_VK, SHIFT_SCAN, KEYEVENTF_SCANCODE)
    for vk, scan in shifted:
        _send_key(vk, scan, up=False)
    time.sleep(SHIFT_HOLD)
    # Release Shift while keeping the Note Keys held down
    _send_input(SHIFT_VK, SHIFT_SCAN, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)

def release_keys(chars):
    lift = []
    for char_in in chars:
        if not char_in: continue
        vk, scan, _ = _lookup(char_in)
        if _held[scan] == 0:
            continue # Already lifted by release_all
        _held[scan] -= 1
        # Only lift the key once no other note is still using it
        if _held[scan] == 0:
            lift.append((vk, scan))
    _wait_for_keys(scan for _, scan in lift)
    for vk, scan in lift:
        _send_key(vk, scan, up=True)

def release_all():
    """Lifts every key still held, e.g. when playback pauses or ends."""
    for scan, count in _held.items():
        if count > 0:
            _send_key(0, scan, up=True)
    _held.clear()

def press_key(char_in):
    press_keys([char_in])

def release_key(char_in):
    release_keys([char_in])
