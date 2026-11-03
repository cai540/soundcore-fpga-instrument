"""Re-read supplied score main notes; old lyric times are coarse locators only.

This tool neither reads old generated MIDI/CSV nor any new predictions.
Labels must never be imported by the audio runtime.
"""
from pathlib import Path
import hashlib
import json


FIRST = [72, 74, 72, 70, 69, 67, 65, 60]
SECOND = [65, 69, 77, 76, 74, 69, 72]
THIRD = [74, 76, 74, 72, 70, 69, 67, 62]
FOURTH = [64, 62, 60, 72, 65, 67, 69]
RIVER = [65, 69, 77, 76, 79, 77, 74]
SMOKE_AND_VILLAGE = [77, 76, 74, 72, 74, 72, 70, 69]
CHORUS_A = [77, 79, 81, 79, 77, 74, 76, 74, 69, 72]
CHORUS_B = [77, 79, 81, 79, 77, 74, 76, 72, 69, 74]
MOTHER = [72, 70, 69, 67, 64, 62, 62, 60, 69]
TELL = [70, 67, 65, 65]


def main():
    source = Path('songs/product_song_review/wodezuguo_lyrics.json')
    score = Path('songs/source/wodezuguo_score_20261026.jpg')
    locator = json.loads(source.read_text(encoding='utf8'))
    reference = [
        (FIRST, SECOND), (THIRD, FOURTH), (FIRST, RIVER),
        (SMOKE_AND_VILLAGE, [64, 62, 60, 67, 65]),
        (CHORUS_A, CHORUS_B), (MOTHER, TELL),
        (FIRST, SECOND), (THIRD, FOURTH), (FIRST, RIVER),
        (SMOKE_AND_VILLAGE, [64, 62, 60, 60, 67, 65]),
        (CHORUS_A, CHORUS_B), (MOTHER, TELL),
        (CHORUS_A, CHORUS_B),
        ([72, 70, 69, 67, 64, 62, 60, 69], [72, 79, 77, 77]),
    ]
    assert len(reference) == len(locator['phrases'])
    phrases = []
    for pair, pitches in zip(locator['phrases'], reference):
        words = [w for w in locator['words'] if w['phrase'] == pair['id']]
        cut = len(pair['line1'])
        for line, ps, group in zip(['line1', 'line2'], pitches, [words[:cut], words[cut:]]):
            assert ''.join(w['char'] for w in group) == pair[line]
            phrases.append({'text': pair[line],
                'source_span_s': [round(group[0]['begin'] - .18, 3), round(group[-1]['end'] + .18, 3)],
                'pitches': ps})
    result = {'split': 'complete_score_review',
        'provenance': 'Main-note sequences independently re-read from user supplied numbered score, printed 1=Eb, source performance 1=F. Original held-note ties count once; distinct same-pitch lyric syllables count separately. Previous curated notes/MIDI were not read. Previously prepared lyric begin/end values are only coarse source locators.',
        'source_score_sha256': hashlib.sha256(score.read_bytes()).hexdigest(),
        'source_locator_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'timing_gold_available': False,
        'annotation_caveat': 'This is a score-based main-note audit, not independently verified millisecond timing or a new-singer generalization benchmark. Part of the first verse was used for development.',
        'cases': [{'id': 'zuguo_complete_vocals', 'recording_id': 'zuguo',
            'complete_vocal_annotation': True, 'source_offset_s': 0,
            'observations': 'zuguo/observations.npz',
            'audio': 'songs/source/wodezuguo_vocals_20261026.mp3',
            'vocal_spans_s': [[47.0, 205.8]], 'phrases': phrases}]}
    out = Path('evaluation/transcription/zuguo_complete_score.json')
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(len(phrases), 'phrases', sum(len(p['pitches']) for p in phrases), 'score main notes')


if __name__ == '__main__':
    main()
