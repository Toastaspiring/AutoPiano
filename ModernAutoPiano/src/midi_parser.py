import mido
import json

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

def parse_midi(midi_file_path, mapping_str, selected_indices=None):
    """
    Parses a MIDI file and returns a list of (wait_time, key_char) tuples.
    selected_indices: List of integers representing track indices to include. If None, all are included.
    """
    midi = mido.MidiFile(midi_file_path)
    
    if selected_indices is None:
        # Iterate over the file object — mido converts ticks → seconds automatically
        message_iterator = midi
    else:
        valid_indices = [i for i in selected_indices if 0 <= i < len(midi.tracks)]
        if not valid_indices:
            message_iterator = midi
        else:
            # Build a temporary MidiFile so that mido's __iter__ handles the
            # tick→second conversion (including tempo changes) correctly.
            # merge_tracks() alone returns raw tick-based times — wrong for playback.
            tmp = mido.MidiFile(type=1, ticks_per_beat=midi.ticks_per_beat)
            # Always include track 0 (tempo / time-signature messages) so the
            # conversion is accurate, unless it's already selected.
            if midi.tracks and 0 not in valid_indices:
                tmp.tracks.append(midi.tracks[0])
            for i in valid_indices:
                tmp.tracks.append(midi.tracks[i])
            message_iterator = tmp

    processed_events = []
    accumulated_time = 0.0
    
    for msg in message_iterator:
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
            # Logic from legacy pyMIDI.py
            # map = key - 23 - 12 - 1 = key - 36
            # It wraps octaves if out of range.
            
            idx = note - 36
            
            # Wrap around if out of bounds (Octave folding)
            while idx >= len(mapping_str):
                idx -= 12
            while idx < 0:
                idx += 12
                
            if 0 <= idx < len(mapping_str):
                char = mapping_str[idx]
                processed_events.append((accumulated_time, action, char))
                accumulated_time = 0.0

    return processed_events

