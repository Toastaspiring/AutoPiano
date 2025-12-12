# ModernAutoPiano

A high-performance, Python-based MIDI automation tool designed for simulating piano input in games and applications such as Virtual Piano and Roblox. This project modernizes legacy automation scripts by implementing robust MIDI parsing, precise event timing, and hardware-level input simulation using the Windows API.

## Features

*   **Hardware-Level Input Simulation**: Uses `Scan Codes` via `SendInput` API to mimic physical keyboard driver events, ensuring compatibility with games that block or ignore standard Virtual Key inputs (e.g., Roblox, DirectInput games).
*   **Accurate Polyphony**: Handles simultaneous note presses and proper note durations (press and release events) rather than simple taps.
*   **Smart Parsing**: Converts MIDI files into a linear event stream of `Note On` and `Note Off` actions.
*   **Configurable Mapping**: Supports custom key mappings for different virtual piano layouts.

## Technical Architecture

The project is structured as a modular Python package:

```
ModernAutoPiano/
├── src/
│   ├── main.py          # CLI Entry point and extensive error handling
│   ├── player.py        # Playback engine with pause/resume support
│   ├── midi_parser.py   # MIDI to Event Stream conversion
│   └── input_sim.py     # Low-level Windows API integration
├── config/
│   └── mappings.json    # Key configuration
└── run.py               # Bootstrap script
```

### 1. Low-Level Input Simulation (`input_sim.py`)

To bypass anti-cheat protections or specific input handling in games, we define specific C-structures compatible with the Windows `user32.dll`. We explicitly use **Scan Codes** (`KEYEVENTF_SCANCODE`) which represent the physical location of a key on the keyboard, and `VkKeyScanW` to correctly map characters to their Virtual Keys and Shift states.

**Key Implementation Details:**

We define the `INPUT` union to support Keyboard, Mouse, and Hardware inputs, ensuring the memory footprint matches what the Windows API expects (fixing legacy `Error 87` issues).

```python
class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = (("mi", MOUSEINPUT),
                    ("ki", KEYBDINPUT),
                    ("hi", HARDWAREINPUT))
    _anonymous_ = ("_input",)
    _fields_ = (("type", wintypes.DWORD), ("_input", _INPUT))
```

The input injection logic sends specific hardware scan codes:

```python
def press_key(char_in):
    # Retrieve Virtual Key and Shift requirement
    vk, needs_shift = get_vk_info(char_in)
    # Map to Hardware Scan Code
    scan = get_scan_code(vk)
    
    if needs_shift:
        # Inject Shift Press + Key Press
        _send_input(0xA0, get_scan_code(0xA0), KEYEVENTF_SCANCODE)
        _send_input(vk, scan, KEYEVENTF_SCANCODE)
        # Release Shift immediately to prevent "Shift Lock" artifacts 
        # while keeping the Note Key held down.
        _send_input(0xA0, get_scan_code(0xA0), KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)
    else:
        _send_input(vk, scan, KEYEVENTF_SCANCODE)
```

### 2. MIDI Event Stream Parsing (`midi_parser.py`)

Unlike simple parsers that effectively "print" notes, we generate a precise timeline of actions. This allows us to hold keys for their exact duration.

```python
# Generates a list of: (wait_time, action_type, character)
# Example:
#   (0.0, 'down', 't')  -> Press 't'
#   (0.5, 'up',   't')  -> Wait 0.5s, then Release 't'
```

We accumulate delta times from the MIDI track to ensure synchronization is maintained even when skipping non-note events.

## Installation and Usage

### Prerequisites

*   Python 3.x
*   Windows OS (for `ctypes` WinAPI support)
*   **Administrator Privileges**: Required for `SendInput` to interact with elevated game windows.

### Setup

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Place your MIDI files in `../Midi` (at the root of the workspace) or configure the path in `src/main.py`.

### Running the Application

**IMPORTANT**: You must run the terminal as **Administrator**.

```bash
python run.py
```

1.  Select a MIDI file from the list.
2.  Switch focus to your target application (e.g., Notepad, Roblox).
3.  Press **DELETE** to Start/Pause playback.
4.  Press **ESC** to Quit.

## Configuration

modify `config/mappings.json` to change the key-to-note mapping string.
