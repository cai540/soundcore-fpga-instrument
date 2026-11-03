"""Apply a frozen decoder to independent labels; never fit a coefficient."""
from pathlib import Path
import argparse
import hashlib
import json
from soundcore_audio.pipeline import Transcriber, load_evidence, export
from soundcore_audio.types import DecodeConfig
from .metrics import evaluate, song_pitch_gate, METRIC_VERSION


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--labels', type=Path, required=True)
    p.add_argument('--observations', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    config_bytes = args.config.read_bytes()
    config = DecodeConfig(**json.loads(config_bytes))
    data = json.loads(args.labels.read_text(encoding='utf8'))
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in data['cases']:
        path = args.observations / Path(case['observations']).parent.name / 'observations.npz'
        notes, _ = Transcriber(None, config).transcribe(load_evidence(path))
        rows.append(evaluate(notes, case))
        export(notes, args.output / case['id'])
    source = Path('soundcore_audio')
    report = {'split': data['split'], 'cases': rows, 'metric_version': METRIC_VERSION,
        'config_sha256': hashlib.sha256(config_bytes).hexdigest(),
        'labels_sha256': hashlib.sha256(args.labels.read_bytes()).hexdigest(),
        'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')},
        'pitch_threshold_passed': all(r['pitch_precision'] >= .9 and r['pitch_recall'] >= .9 for r in rows),
        'timing_gold_available': data['timing_gold_available'],
        'whole_song_or_general_population_accuracy_measured': False,
        'requested_song_pitch_gate': song_pitch_gate(rows),
        'product_acceptance_passed': False}
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: report[k] for k in ['split', 'pitch_threshold_passed', 'product_acceptance_passed']}))
    for row in rows:
        print(row['id'], row['correct'], row['wrong_pitch'], row['missed'], row['extra'],
              row['pitch_precision'], row['pitch_recall'])


if __name__ == '__main__':
    main()
