import ctypes
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

# One physical key carries two notes: 't' on its own and 'T' under Shift. The
# key can only be in one state, so the two can never be *held* together. But
# the piano starts a note on key-down and lets it ring, so a whole chord goes
# out as ONE SendInput call: Windows stamps every event with the same time and
# the game sees them on a single frame. Inside that batch the black notes are
# struck first, then the white keys go down and stay down, so notes still
# sustain for as long as the MIDI holds them.

def _send_batch(events):
    """events: a list of (scan_code, is_key_up), delivered as one atomic call."""
    events = list(events)
    if not events:
        return
    arr = (INPUT * len(events))()
    for i, (scan, up) in enumerate(events):
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
        arr[i] = INPUT(type=INPUT_KEYBOARD,
                       ki=KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags))
    sent = user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))
    if sent != len(events):
        print(f"[InputErr] SendInput sent {sent}/{len(events)}. Error: {ctypes.get_last_error()}")

def _lookup(char_in):
    # Check manual map first (Force QWERTY)
    if char_in in QWERTY_MAP:
        return QWERTY_MAP[char_in] # (scan code, needs shift)
    # Fallback to system layout
    vk, needs_shift = get_vk_info(char_in)
    return get_scan_code(vk), needs_shift

# Character -> how many notes of the MIDI are sounding it right now
_sounding = Counter()
# Scan code -> the character whose key is physically down, if any
_key_owner = {}

def press_keys(chars):
    """
    Starts every note of one chord in a single batch, so they share a timestamp.
    Keys stay down afterwards and sustain until release_keys lifts them. The one
    exception is a key whose two notes are both in the chord: the black note is
    struck and left to ring so the white note can hold the key.
    """
    shifted, plain, seen = [], [], set()
    for char_in in chars:
        if not char_in:
            continue
        _sounding[char_in] += 1
        if char_in in seen:
            continue # The same note twice in one chord is still one key press
        seen.add(char_in)
        scan, needs_shift = _lookup(char_in)
        (shifted if needs_shift else plain).append((char_in, scan))

    plain_scans = {scan for _, scan in plain}
    events = []

    # A key that is already down must come up first, either to re-strike its own
    # note or to free it for the other note sharing it.
    for scan in dict.fromkeys(scan for _, scan in shifted + plain):
        if scan in _key_owner:
            events.append((scan, True))
            del _key_owner[scan]

    if shifted:
        events.append((SHIFT_SCAN, False))
        for char_in, scan in shifted:
            events.append((scan, False))
            if scan in plain_scans:
                events.append((scan, True)) # Struck and left ringing
            else:
                _key_owner[scan] = char_in
        events.append((SHIFT_SCAN, True))

    for char_in, scan in plain:
        events.append((scan, False))
        _key_owner[scan] = char_in

    _send_batch(events)

def release_keys(chars):
    events = []
    for char_in in chars:
        if not char_in or _sounding[char_in] == 0:
            continue
        _sounding[char_in] -= 1
        if _sounding[char_in]:
            continue # Another note of the MIDI is still holding this key
        scan, _ = _lookup(char_in)
        if _key_owner.get(scan) == char_in:
            events.append((scan, True))
            del _key_owner[scan]
    _send_batch(events)

def release_all():
    """Lifts Shift and every key still down, e.g. when playback pauses or ends."""
    events = [(scan, True) for scan in _key_owner] + [(SHIFT_SCAN, True)]
    _key_owner.clear()
    _sounding.clear()
    _send_batch(events)

def press_key(char_in):
    press_keys([char_in])

def release_key(char_in):
    release_keys([char_in])
