"""Fit one small decoder configuration using the development split only.

This module is evaluation tooling. It cannot add runtime song cases, and the
runtime never imports it or the labeled data. The held-out file is not read.
"""
from dataclasses import asdict
from itertools import product
from pathlib import Path
import argparse
import hashlib
import json
from soundcore_audio.pipeline import Transcriber, load_evidence
from soundcore_audio.types import DecodeConfig
from .metrics import evaluate, METRIC_VERSION


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--development', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--observations', type=Path,
                   help='Prepared output root; labels stay independent of model artifacts')
    args = p.parse_args()
    data = json.loads(args.development.read_text(encoding='utf8'))
    if data['split'] != 'development':
        raise ValueError('Calibration accepts only the development split')
    cases = [(case, load_evidence(args.observations / Path(case['observations']).parent.name / 'observations.npz'
              if args.observations else case['observations'])) for case in data['cases']]
    results = []
    for neural, phone, birth, key, acoustic, duration in product([.25, .5, 1.], [0., .5],
            [.5, 1., 2.], [1.], [0., .5, 1.], [0., .5, 1.]):
        config = DecodeConfig(neural_boundary_weight=neural, phonetic_boundary_weight=phone, note_cost=birth,
                              tonality_weight=key, acoustic_pitch_weight=acoustic, duration_weight=duration)
        transcriber = Transcriber(None, config)
        rows = []
        for case, evidence in cases:
            notes, _ = transcriber.transcribe(evidence)
            rows.append(evaluate(notes, case))
        results.append({'config': asdict(config), 'worst_case_f1': min(r['pitch_f1'] for r in rows),
            'minimum_precision': min(r['pitch_precision'] for r in rows),
            'minimum_recall': min(r['pitch_recall'] for r in rows), 'cases': rows})
    results.sort(key=lambda r: (min(r['minimum_precision'], r['minimum_recall']),
                                r['worst_case_f1'], -sum(r['config'][k] for k in
                                ['phonetic_boundary_weight', 'tonality_weight'])), reverse=True)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'development_search.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf8')
    (args.output / 'decoder.json').write_text(json.dumps(results[0]['config'], indent=2), encoding='utf8')
    (args.output / 'provenance.json').write_text(json.dumps({
        'development_labels_sha256': hashlib.sha256(args.development.read_bytes()).hexdigest(),
        'metric_version': METRIC_VERSION,
        'metric_sha256': hashlib.sha256(Path(__file__).with_name('metrics.py').read_bytes()).hexdigest(),
        'heldout_labels_read': False, 'selected': {k: results[0][k] for k in
        ['minimum_precision', 'minimum_recall', 'worst_case_f1']},
        'metric': 'ordered main-note pitch precision/recall, not rhythm accuracy',
    }, indent=2), encoding='utf8')
    print(json.dumps({k: results[0][k] for k in ['config', 'minimum_precision', 'minimum_recall']}, indent=2))


if __name__ == '__main__':
    main()
