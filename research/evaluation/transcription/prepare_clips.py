"""Prepare acoustic observations from source clips without reading labels."""
from pathlib import Path
import argparse
import hashlib
from soundcore_audio.audio import Audio, decode
from soundcore_audio.game import GameModel
from soundcore_audio.features import WordObserver
from soundcore_audio.pitch import PitchObserver
from soundcore_audio.pipeline import Transcriber, export, save_evidence
import json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--clips', type=Path, required=True)
    p.add_argument('--models', type=Path, required=True)
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--words', type=Path, required=True)
    p.add_argument('--pitch', type=Path, required=True)
    args = p.parse_args()
    model = GameModel(args.models, args.cache)
    words = WordObserver(args.words)
    pitch = PitchObserver(args.pitch, args.cache)
    transcriber = Transcriber(model, word_observer=words, pitch_observer=pitch)
    for item in json.loads(args.clips.read_text(encoding='utf8')):
        source = decode(item['audio'], model.rate)
        first = round(item['start_s'] * model.rate)
        last = round((item['start_s'] + item['duration_s']) * model.rate)
        recording = Audio(source.samples[first:last], source.rate)
        evidence = transcriber.prepare(recording, lambda i, n: print(item['id'], i, n, flush=True))
        notes, audit = transcriber.transcribe(evidence)
        out = args.output / item['id']
        export(notes, out)
        save_evidence(evidence, out / 'observations.npz')
        (out / 'audit.json').write_text(json.dumps(audit, indent=2), encoding='utf8')
        (out / 'provenance.json').write_text(json.dumps({
            'clip': item, 'source_pcm_sha256': evidence.source_sha256,
            'observers': dict(evidence.observers),
            'observations_sha256': hashlib.sha256((out / 'observations.npz').read_bytes()).hexdigest(),
            'runtime_source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in Path('soundcore_audio').glob('*.py')},
            'runtime_lyrics_or_scores_used': False, 'accepted': False,
        }, ensure_ascii=False, indent=2), encoding='utf8')
        print(item['id'], len(notes), 'notes', flush=True)


if __name__ == '__main__':
    main()
