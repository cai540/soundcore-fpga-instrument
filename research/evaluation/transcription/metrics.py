"""Ordered main-note metrics, not calibrated rhythm or whole-song accuracy."""

METRIC_VERSION = 'ordered-main-pitch-vocal-scope-edit-errors-v3'


def align(expected, observed):
    cells = {(0, 0): (0, ())}
    for i in range(len(expected) + 1):
        for j in range(len(observed) + 1):
            if i == j == 0:
                continue
            options = []
            if i and j:
                cost, path = cells[i - 1, j - 1]
                operation = 'correct' if expected[i - 1] == observed[j - 1] else 'wrong_pitch'
                options.append((cost + (operation != 'correct'), path + (operation,)))
            if i:
                cost, path = cells[i - 1, j]
                options.append((cost + 1, path + ('missed',)))
            if j:
                cost, path = cells[i, j - 1]
                options.append((cost + 1, path + ('extra',)))
            cells[i, j] = min(options, key=lambda v: v[0])
    _, path = cells[len(expected), len(observed)]
    return {key: path.count(key) for key in ('correct', 'wrong_pitch', 'missed', 'extra')}


def summarize(counts):
    expected = counts['correct'] + counts['wrong_pitch'] + counts['missed']
    observed = counts['correct'] + counts['wrong_pitch'] + counts['extra']
    precision = counts['correct'] / max(observed, 1)
    recall = counts['correct'] / max(expected, 1)
    errors = counts['wrong_pitch'] + counts['missed'] + counts['extra']
    return {**counts, 'reference_notes': expected, 'predicted_notes': observed,
            'pitch_precision': precision, 'pitch_recall': recall,
            'pitch_f1': 2 * precision * recall / max(precision + recall, 1e-12),
            'strict_note_accuracy': max(0., 1 - errors / max(expected, 1)),
            'note_error_rate': errors / max(expected, 1),
            'rhythm_accuracy_measured': False}


def evaluate(notes, case):
    totals = {key: 0 for key in ('correct', 'wrong_pitch', 'missed', 'extra')}
    phrases = []
    assigned = [[] for _ in case['phrases']]
    for note in notes:
        start = note.start_ms / 1000 + case['source_offset_s']
        end = note.end_ms / 1000 + case['source_offset_s']
        vocal_spans = case.get('vocal_spans_s')
        if vocal_spans is not None and not any(min(end, b) > max(start, a) for a, b in vocal_spans):
            continue
        overlaps = [max(0., min(end, p['source_span_s'][1]) - max(start, p['source_span_s'][0]))
                    for p in case['phrases']]
        if max(overlaps, default=0.) > 0:
            # Outer spans are coarse locators, not millisecond onset gold.
            # A note starting 10 ms before a phrase must not disappear, nor
            # may one held note be counted in two neighboring phrases.
            assigned[max(range(len(overlaps)), key=overlaps.__getitem__)].append(note.midi)
        elif vocal_spans is not None and case['phrases']:
            # A false release/echo inside the annotated vocal block must not
            # disappear merely because it falls in the breath between lines.
            distances = [max(p['source_span_s'][0] - end, start - p['source_span_s'][1], 0.)
                         for p in case['phrases']]
            assigned[min(range(len(distances)), key=distances.__getitem__)].append(note.midi)
    for reference, predicted in zip(case['phrases'], assigned):
        counts = align(reference['pitches'], predicted)
        for key in totals:
            totals[key] += counts[key]
        phrases.append({'text': reference['text'], 'expected': reference['pitches'],
                        'observed': predicted, **summarize(counts)})
    return {'id': case['id'], 'recording_id': case.get('recording_id', case['id']),
            'complete_vocal_annotation': bool(case.get('complete_vocal_annotation') and case.get('vocal_spans_s')),
            **summarize(totals), 'phrases': phrases}


def song_pitch_gate(rows):
    """One complete song >=99%, two other complete songs >=95%.

    Partial phrases and two sections of the same recording cannot become
    three passing songs. This gate alone does not validate rhythm/listening.
    """
    songs = {}
    for row in rows:
        if row.get('complete_vocal_annotation') and row['reference_notes']:
            key = row.get('recording_id', row['id'])
            songs[key] = min(songs.get(key, 1.), row['strict_note_accuracy'])
    scores = sorted(songs.values(), reverse=True)
    passed = len(scores) >= 3 and scores[0] >= .99 and scores[1] >= .95 and scores[2] >= .95
    return {'required_strict_note_accuracy': [.99, .95, .95],
            'complete_song_scores': songs, 'fully_annotated_songs': len(songs),
            'voice_pitch_gate_passed': passed, 'rhythm_gate_measured': False}
