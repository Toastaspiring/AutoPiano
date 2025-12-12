import ctypes
import time
import sys

# Definitions
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_UNICODE = 0x0004

from ctypes import wintypes

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

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = (("ki", KEYBDINPUT),)
    _anonymous_ = ("_input",)
    _fields_ = (("type", wintypes.DWORD), ("_input", _INPUT))

user32 = ctypes.WinDLL('user32', use_last_error=True)

def send_scancode(vk):
    # Map VK to ScanCode
    sc = user32.MapVirtualKeyW(vk, 0)
    
    # Press
    inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=sc, dwFlags=KEYEVENTF_SCANCODE))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    time.sleep(0.05)
    # Release
    inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=sc, dwFlags=KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def send_vk(vk):
    # Press
    inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    time.sleep(0.05)
    # Release
    inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def main():
    print("Debug Input Tool")
    print("1. Test Virtual Key (VK) input")
    print("2. Test Scan Code input")
    choice = input("Select mode (1/2): ")
    
    print("You have 5 seconds to focus Notepad or the Game...")
    for i in range(5, 0, -1):
        print(i)
        time.sleep(1)
    
    print("Typing 'TEST'...")
    keys = [0x54, 0x45, 0x53, 0x54] # T, E, S, T
    
    for k in keys:
        if choice == '1':
            send_vk(k)
        else:
            send_scancode(k)
        time.sleep(0.1)
        
    print("Done.")

if __name__ == "__main__":
    main()
