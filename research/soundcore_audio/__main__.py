"""python -m soundcore_audio audio.mp3 --models PATH --output PATH"""
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
from .audio import decode
from .game import GameModel
from .features import WordObserver
from .pitch import PitchObserver
from .pipeline import Transcriber, export, save_evidence
from .types import DecodeConfig


def main():
    parser = argparse.ArgumentParser(description='Local single-voice transcription')
    parser.add_argument('audio', type=Path)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--words', type=Path, required=True)
    parser.add_argument('--pitch', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=Path('.audio_models/cache'))
    parser.add_argument('--config', type=Path, required=True,
                        help='Explicit experimental decoder configuration; no silent release default')
    args = parser.parse_args()
    config = DecodeConfig(**json.loads(args.config.read_text(encoding='utf8')))
    source = Path(__file__).parent
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')}
    model = GameModel(args.models, args.cache)
    words = WordObserver(args.words)
    pitch = PitchObserver(args.pitch, args.cache)
    transcriber = Transcriber(model, config, words, pitch)
    recording = decode(args.audio, model.rate)
    evidence = transcriber.prepare(recording, lambda i, n: print('phrase', i, '/', n, flush=True))
    notes, audit = transcriber.transcribe(evidence)
    if hashes != {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')}:
        raise RuntimeError('Transcription source changed during inference; rerun the finished version')
    export(notes, args.output)
    save_evidence(evidence, args.output / 'observations.npz')
    (args.output / 'audit.json').write_text(json.dumps(audit, indent=2), encoding='utf8')
    (args.output / 'manifest.json').write_text(json.dumps({
        'source_pcm_sha256': evidence.source_sha256, 'duration_ms': evidence.duration_ms,
        'notes': len(notes), 'models_sha256': model.fingerprints, 'config': asdict(config),
        'word_observer': words.metadata,
        'pitch_observer': pitch.metadata,
        'source_sha256': hashes,
        'runtime_reference_scores_or_lyrics_used': False, 'postprocessing_corrections': 0,
    }, indent=2), encoding='utf8')
    print('saved', args.output, len(notes), 'notes', flush=True)


if __name__ == '__main__':
    main()
