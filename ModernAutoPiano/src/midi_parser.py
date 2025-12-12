import mido
import json
import os

def load_mapping(config_path):
    with open(config_path, 'r') as f:
        data = json.load(f)
    return data["mapping"]

def parse_midi(midi_file_path, mapping_str):
    """
    Parses a MIDI file and returns a list of (wait_time, key_char) tuples.
    """
    midi = mido.MidiFile(midi_file_path)
    tempo = 500000  # Default 120 BOM
    notes = []
    
    # We need to linearize the track
    # mido's 'play()' yields messages with proper delta times converted to seconds
    # but we want to pre-process to mapped characters.
    
    # However, play() blocks. We want to extract.
    # Let's iterate through all messages in absolute time or just use mido's merge_tracks if available
    # or iterate tracks and sort.
    # For simplicity, let's use the legacy approach: linearize with absolute times then sort?
    # Or better: use mido.MidiFile given it's a generator.
    
    # Actually, mido has a helper for this.
    
    output_events = []
    
    # We need to map MIDI note numbers (21-108) to our mapping string.
    # The mapping string length is 61 keys usually (C2 to C7 approx).
    # Legacy code: note - 21.
    
    # Merge tracks to a single stream of absolute messages
    # MidiFile passed to 'for' yields messages in order if we don't mess with it?
    # Actually, iterating over MidiFile merges tracks automatically.
    
    # We want a list of actions:
    # Action: (wait_time_from_prev, type, key)
    # type: 'down', 'up'
    
    events = []
    
    # Track current active notes to ignoring duplicates if necessary
    # or just straight mapping.
    
    # Mido's iteration yields delta time.Perfect.
    # But filtering tracks might mess up time? No, mido handles it.
    
    for msg in midi:
        # msg.time is delta time (seconds)
        
        # We need to preserve time for non-note messages too!
        # If we skip a message, we must add its time to the next one.
        # But here we are constructing a timeline list.
        # So we can just append a 'wait' event or attach time to the next action.
        
        delta = msg.time
        
        # If the message is Note On/Off
        event_type = None
        char = None
        
        if msg.type == 'note_on' and msg.velocity > 0:
            event_type = 'down'
            note = msg.note
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            event_type = 'up'
            note = msg.note
            
        if event_type:
            # Map note
            if 21 <= note <= 108:
                idx = note - 21
                if 0 <= idx < len(mapping_str):
                    char = mapping_str[idx]
            
            if char:
                events.append({'delay': delta, 'action': event_type, 'key': char})
                continue
                
        # If we didn't emit an event, we need to add this delta to the NEXT event.
        # But better: just add a "Wait" event? Or simpler: accumulate.
        
        # Accumulation Logic:
        # If events list is empty, just hold it? No.
        # If we add an event, we use 'delta'.
        # If we don't, we add 'delta' to an accumulator.
        # But we modify the 'delta' of the NEXT event.
        
        # Wait, that's complex since we are iterating forward.
        # Alternative: Just emit "Wait" events?
        # No, let's accumulate.
        
        if events:
            # Add this delta to the next event we create? 
            # No, we don't have the next event yet.
            # We add it to a "pending_time" variable.
            pass
            
    # Let's restart the loop with accumulation
    
    processed_events = []
    accumulated_time = 0.0
    
    for msg in midi:
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
