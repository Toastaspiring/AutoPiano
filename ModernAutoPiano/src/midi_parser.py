import mido
import json
import os
from collections import Counter, defaultdict, deque

def load_mapping(config_path):
    with open(config_path, 'r') as f:
        data = json.load(f)
    return data["mapping"]

def get_tracks_info(midi_file_path):
    """
    Returns a list of dicts: {'name': str, 'is_drum': bool, 'is_piano': bool, 'instrument': str}
    """
    midi = mido.MidiFile(midi_file_path)
    infos = []
    
    # Instruments map (simplified General MIDI)
    GM_FAMILIES = [
        "Piano", "Percussion", "Organ", "Guitar", "Bass", "Strings", "Ensemble",
        "Brass", "Reed", "Pipe", "Synth Lead", "Synth Pad", "Synth FX", "Ethnic",
        "Percussive", "SFX"
    ]
    
    for i, track in enumerate(midi.tracks):
        name = f"Track {i}"
        is_drum = False
        programs = set()
        
        # Scan track
        for msg in track:
            if msg.type == 'track_name':
                name = f"Track {i}: {msg.name}"
            
            # Check for Channel 10 (drums)
            if hasattr(msg, 'channel') and msg.channel == 9:
                is_drum = True
            
            # Check Program Change
            if msg.type == 'program_change':
                programs.add(msg.program)
                
        # Heuristic for drums by name
        name_lower = name.lower()
        drum_keywords = ["drum", "percussion", "kit", "ride", "cymbal", "brsh", "toms", "hihat", "crash"]
        if any(kw in name_lower for kw in drum_keywords):
            is_drum = True
            
        # Determine Instrument
        instrument_label = "Unknown"
        is_piano = False
        
        if is_drum:
             instrument_label = "Drums"
        elif programs:
             # Just take the first one or analyze?
             # If any program is 0-7, let's call it Piano-like
             # General MIDI: 0-7 is Piano
             prog = list(programs)[0] # Take first for label
             family_idx = prog // 8
             if 0 <= family_idx < len(GM_FAMILIES):
                 instrument_label = GM_FAMILIES[family_idx]
             
             # Check if ANY program is Piano
             for p in programs:
                 if 0 <= p <= 7:
                     is_piano = True
                     break
        else:
             # No program change? Usually defaults to Piano (0)
             is_piano = True
             instrument_label = "Default (Piano)"
             
        infos.append({
            'name': name,
            'is_drum': is_drum,
            'is_piano': is_piano,
            'instrument': instrument_label
        })
    return infos

def _key_index(note, mapping_len):
    idx = note - 36
    # Wrap around if out of bounds (Octave folding)
    while idx >= mapping_len:
        idx -= 12
    while idx < 0:
        idx += 12
    return idx

def _is_shifted(char):
    # Black keys are the uppercase letters and the symbols (!, @, $...)
    return not (char.islower() or char.isdigit())

def best_transpose(midi_file_path, mapping_str, selected_indices=None):
    """
    Returns the shift in semitones that puts the fewest notes on black (Shift) keys.
    Virtual Piano sheets do the same, e.g. Take Five in Eb minor is written in A minor:
    81% of its notes need Shift as written, 6% after a +6 shift. The game reads
    Shift late, so every black key avoided is one that can't come out wrong or late.
    """
    target_midi = _load_tracks(midi_file_path, selected_indices)
    notes = [msg.note for track in target_midi.tracks for msg in track
             if msg.type == 'note_on' and msg.velocity > 0]
    if not notes:
        return 0
    mapping_len = len(mapping_str)

    def cost(shift):
        black = sum(1 for n in notes if _is_shifted(mapping_str[_key_index(n + shift, mapping_len)]))
        # Folded notes can land on keys already in use, so prefer shifts that fit the range
        folded = sum(1 for n in notes if not 0 <= n + shift - 36 < mapping_len)
        return (black, folded, abs(shift))

    return min(range(-6, 7), key=cost)

def _move_twin_clashes(events, mapping_str):
    """
    A black key shares its physical key with the white key below it (q/Q, 1/!),
    so the two can't sound together: playing one lifts the other. When a note's
    twin is already down, play the note an octave away on a free key instead, so
    both ring. Take Five has 76 such clashes after transposing, e.g. A4 + A#4.
    """
    index = {c: i for i, c in enumerate(mapping_str)}

    def physical(char):
        i = index[char]
        return mapping_str[i - 1] if _is_shifted(char) else char

    down_on = defaultdict(Counter) # physical key -> chars currently down on it
    played_as = defaultdict(deque) # char from the MIDI -> char actually used, per note still down
    out = []
    for wait, action, char in events:
        actual = char
        if action == 'down':
            on_key = down_on[physical(char)]
            if any(n > 0 and c != char for c, n in on_key.items()):
                # Move away from the twin: black keys sit above theirs, white keys below
                for step in ((12, -12) if _is_shifted(char) else (-12, 12)):
                    j = index[char] + step
                    if 0 <= j < len(mapping_str) and not any(down_on[physical(mapping_str[j])].values()):
                        actual = mapping_str[j]
                        break
            played_as[char].append(actual)
            down_on[physical(actual)][actual] += 1
        elif played_as[char]:
            actual = played_as[char].popleft()
            down_on[physical(actual)][actual] -= 1
        out.append((wait, action, actual))
    return out

def _load_tracks(midi_file_path, selected_indices):
    original_midi = mido.MidiFile(midi_file_path)
    
    # We must construct a new MidiFile to ensure 'ticks' are converted to 'seconds'
    # correctly using the Temp Map (Track 0).
    target_midi = mido.MidiFile(ticks_per_beat=original_midi.ticks_per_beat)
    
    if selected_indices is None:
        target_midi.tracks = original_midi.tracks
    else:
        valid_indices = set([i for i in selected_indices if 0 <= i < len(original_midi.tracks)])
        
        # Handling Track 0 (Tempo Map)
        # Even if Track 0 is not selected (e.g. it's drums), we often need its MetaMessages (Tempo, etc.)
        # If T0 is valid, it will be added in the loop below.
        # If T0 is NOT valid, we add a "Cleaned" version of it (Meta only).
        if 0 not in valid_indices and len(original_midi.tracks) > 0:
            t0 = original_midi.tracks[0]
            cleaned_t0 = mido.MidiTrack()
            for msg in t0:
                # Keep meta messages or sysex, discard notes
                if msg.type not in ['note_on', 'note_off']:
                    cleaned_t0.append(msg)
            target_midi.tracks.append(cleaned_t0)

        # Add selected tracks
        for i in sorted(list(valid_indices)):
            target_midi.tracks.append(original_midi.tracks[i])

    return target_midi

def parse_midi(midi_file_path, mapping_str, selected_indices=None, transpose=0):
    """
    Parses a MIDI file and returns a list of (wait_time, key_char) tuples.
    selected_indices: List of integers representing track indices to include. If None, all are included.
    transpose: semitones added to every note before it is mapped to a key.
    """
    target_midi = _load_tracks(midi_file_path, selected_indices)

    processed_events = []
    accumulated_time = 0.0
    first_note_found = False
    
    # helper for mapping
    mapping_len = len(mapping_str)

    # Iterating a MidiFile yields messages with 'time' in SECONDS
    for msg in target_midi:
        accumulated_time += msg.time
        
        action = None
        char = None
        
        if msg.type == 'note_on' and msg.velocity > 0:
            action = 'down'
            note = msg.note
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            action = 'up'
            note = msg.note
            
        if action:
            # --- Skip Initial Silence Logic ---
            if not first_note_found:
                # If this is the very first note, and we've waited too long, skip it.
                if accumulated_time > 1.0:
                    print(f"[Auto-Skip] Skipped {accumulated_time:.2f}s of silence at start.")
                    accumulated_time = 0.5 # Small buffer
                first_note_found = True
            # ----------------------------------

            idx = _key_index(note + transpose, mapping_len)

            if 0 <= idx < mapping_len:
                char = mapping_str[idx]
                processed_events.append((accumulated_time, action, char))
                accumulated_time = 0.0

    return _move_twin_clashes(processed_events, mapping_str)

