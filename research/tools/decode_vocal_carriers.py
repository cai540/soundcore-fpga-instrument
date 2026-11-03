"""Decode automatic articulation evidence, without loading research code.

The NPZ is an acoustic cache, not a reference score or an edited MIDI.
Upstream observers remain experimental; this command rejects incompatible
or incomplete evidence rather than pretending an alignment succeeded.
"""
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from soundcore_audio.articulation import ArticulationEvidence, CarrierConfig, decode_carriers, align_carrier_timing
from soundcore_audio.pipeline import export

POLICY = 'automatic-vocal-articulation-carriers-v1'


def load_graph(path):
    with np.load(path, allow_pickle=False) as a:
        if 'policy' not in a or str(a['policy']) != POLICY:
            raise ValueError('Incompatible articulation evidence')
        meta = json.loads(str(a['metadata']))
        if meta.get('unit_source') != 'automatic-source-audio':
            raise ValueError('This experiment requires automatic source articulation proposals')
        d = ArticulationEvidence(
            a['cuts'], a['edges'], a['carrier'], a['voiced'], a['boundary_cost'],
            a['phone_likelihood'], a['pitch_boundary'], tuple(meta['units']),
            frozenset(meta['pause_after']), meta['typical_duration_s'], meta['source_sha256'],
            a['content_cost'] if 'content_cost' in a else None)
        prior = a['pitch_prior'].copy()
        f0 = a['f0_likelihood'].copy() if 'f0_likelihood' in a else None
    return d, prior, f0, meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--lock-pitch-input', type=Path,
                   help='Previously confirmed characters.json from the same source; only estimate timing')
    args = p.parse_args()
    d, prior, f0, meta = load_graph(args.evidence)
    config = CarrierConfig(**json.loads(args.config.read_text(encoding='utf8')))
    parent = None
    if args.lock_pitch_input:
        parent = json.loads(args.lock_pitch_input.read_text(encoding='utf8'))
        if parent.get('source_pcm_sha256') != d.source_sha256:
            raise ValueError('The locked pitch path belongs to another recording')
        if tuple(u.get('recognized_unit') for u in parent['units']) != d.units:
            raise ValueError('The locked pitch path uses a different source unit sequence')
        fixed = [[n['midi'] for n in u['notes']] for u in parent['units']]
        result = align_carrier_timing(d, config, fixed)
    else:
        result = decode_carriers(d, config, prior, f0)
    export(result.notes, args.output)
    details = {'units': [{'recognized_unit': text, 'notes': [asdict(n) for n in group]}
                         for text, group in zip(d.units, result.groups)],
               'source_pcm_sha256': d.source_sha256,
               'recognized_lyrics_verified': False,
               'maximum_notes_per_unit': max(map(len, result.groups)),
               'config': asdict(config), 'partition_cost': result.partition_cost,
               'evidence_sha256': hashlib.sha256(args.evidence.read_bytes()).hexdigest(),
               'core_sha256': hashlib.sha256((Path(__file__).resolve().parents[1] / 'soundcore_audio/articulation.py').read_bytes()).hexdigest(),
               'observer_metadata': meta, 'postprocessing_corrections': 0,
               'pitch_path_locked': parent is not None,
               'pitch_parent_sha256': hashlib.sha256(args.lock_pitch_input.read_bytes()).hexdigest() if parent else None,
               'runtime_reference_score_or_lyrics_used': False,
               'accepted': False, 'integrated_in_apk_or_fpga': False}
    (args.output / 'characters.json').write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf8')
    print('saved', len(result.groups), 'units,', len(result.notes), 'carriers', flush=True)


if __name__ == '__main__':
    main()
