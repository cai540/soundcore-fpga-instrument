"""Software/source-clock invariants; no claims of accepted musical quality."""
from pathlib import Path
import csv
import hashlib
import json
import mido

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/vocal_transcription_v9_20261029'


def read(path):
    with path.open(encoding='utf8') as f:
        return [(int(n['start_ms']), int(n['duration_ms']), int(n['midi'])) for n in csv.DictReader(f)]


def union(notes):
    result = []
    for start, duration, pitch in notes:
        if duration <= 0 or not 1 <= pitch <= 127:
            raise AssertionError('Invalid note event')
        if result and start < result[-1][1]:
            raise AssertionError('Overlapping vocal events')
        if result and start == result[-1][1]:
            result[-1][1] = start + duration
        else:
            result.append([start, start + duration])
    return result


def main():
    rows = []
    for recording in ('zuguo', 'qiansixi', 'chilege', 'lantingxu'):
        directory = BASE / 'hybrid' / recording
        manifest = json.loads((directory / 'manifest.json').read_text())
        raw, notes = read(directory / 'raw.csv'), read(directory / 'notes.csv')
        if union(raw) != union(notes):
            raise AssertionError('Existing sounding region/rest changed: ' + recording)
        for leaf, expected in manifest['algorithm_sha256'].items():
            actual = hashlib.sha256((ROOT / 'scripts' / leaf).read_bytes()).hexdigest()
            if actual != expected:
                raise AssertionError('Output made by another source revision: ' + recording + '/' + leaf)
        cursor, active, midi_notes = 0., None, []
        for message in mido.MidiFile(directory / 'source_clock.mid'):
            cursor += message.time
            if message.type == 'note_on' and message.velocity:
                if active is not None:
                    raise AssertionError('Polyphonic output')
                active = (round(cursor * 1000), message.note)
            elif message.type == 'note_off' or (message.type == 'note_on' and not message.velocity):
                if active is None or message.note != active[1]:
                    raise AssertionError('Unpaired MIDI release')
                start, pitch = active
                midi_notes.append((start, round(cursor * 1000) - start, pitch))
                active = None
        if active is not None or midi_notes != notes:
            raise AssertionError('MIDI/source-time discrepancy')
        if notes and notes[-1][0] + notes[-1][1] > manifest['source_ms']:
            raise AssertionError('Events beyond the recording')
        rows.append({'recording': recording, 'source_ms': manifest['source_ms'],
            'raw_notes': len(raw), 'output_notes': len(notes),
            'sounding_union_and_all_original_rests_unchanged': True,
            'midi_millisecond_roundtrip_exact': True, 'source_revision_current': True,
            'pitch_or_listening_accuracy_measured': False})
    result = {'checks': rows, 'apk_or_fpga_updated': False,
              'real_world_90_percent_verified': False, 'accepted': False}
    (BASE / 'hybrid_validation.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
