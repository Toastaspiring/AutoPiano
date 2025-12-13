import mido
import json
import os

def load_mapping(config_path):
    with open(config_path, 'r') as f:
        data = json.load(f)
    return data["mapping"]

def get_tracks_info(midi_file_path):
    """
    Returns a list of dicts: {'name': str, 'is_drum': bool}
    """
    midi = mido.MidiFile(midi_file_path)
    infos = []
    for i, track in enumerate(midi.tracks):
        name = f"Track {i}"
        is_drum = False
        
        # Scan track
        for msg in track:
            if msg.type == 'track_name':
                name = f"Track {i}: {msg.name}"
            
            # Check for Channel 10 (drums)
            # mido channels are 0-15. Channel 10 is index 9.
            if hasattr(msg, 'channel') and msg.channel == 9:
                is_drum = True
                
        # Heuristic: if name matches "Drum" or "Percussion"
        if "drum" in name.lower() or "percussion" in name.lower():
            is_drum = True
            
        infos.append({'name': name, 'is_drum': is_drum})
    return infos

def parse_midi(midi_file_path, mapping_str, selected_indices=None):
    """
    Parses a MIDI file and returns a list of (wait_time, key_char) tuples.
    selected_indices: List of integers representing track indices to include. If None, all are included.
    """
    midi = mido.MidiFile(midi_file_path)
    
    if selected_indices is None:
        # Iterate over the file object merges all tracks
        message_iterator = midi
    else:
        # Filter specific tracks
        valid_indices = [i for i in selected_indices if 0 <= i < len(midi.tracks)]
        if not valid_indices:
            # If selection invalid, fall back to all? Or empty?
            # Let's fallback to all to be safe, or just the first.
            # actually better to return empty if user selected "nothing"
            if selected_indices: # User intended to select but failed
                 print("Warning: Invalid track indices. Playing all.")
                 message_iterator = midi
            else:
                 message_iterator = midi
        else:
            tracks_to_merge = [midi.tracks[i] for i in valid_indices]
            message_iterator = mido.merge_tracks(tracks_to_merge)

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

