"""Explicit v1 -> v2 presence-factor migration of verified native tensors.

The source archive is never modified. Neural pitch/boundary/F0 measurements
are copied unchanged; only independent interval presence is derived from
the original region maxima. Normal runtime loading still rejects v1 files.
"""
from pathlib import Path
import argparse
import hashlib
import importlib
import importlib.util
import json
import sys
import numpy as np
from soundcore_audio.decoder import candidate_cuts, interval_candidates
from soundcore_audio.pipeline import PhraseEvidence, RecordingEvidence, save_evidence, EVIDENCE_POLICY
from soundcore_audio.types import ModelObservation, IntervalEvidence


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suite',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,default=Path('output/vocal_clean_core_20261030'))
    args=parser.parse_args()
    baseline=Path('build/vocal_register_clean_20261030/baseline/soundcore_audio')
    spec=importlib.util.spec_from_file_location('_frozen_native_v1',baseline/'__init__.py',submodule_search_locations=[str(baseline)])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    old_loader=importlib.import_module('_frozen_native_v1.pipeline').load_evidence
    records=[]
    for item in json.loads(args.suite.read_text(encoding='utf8')):
        source=args.source_root/item['id']/'observations.npz'
        old=old_loader(source)
        phrases=[]
        for p in old.phrases:
            obs=ModelObservation(p.observation.cuts,p.observation.boundary_probability,p.observation.pitch_activation)
            lookup={(v.start,v.end):v for v in p.intervals}
            edges=tuple(IntervalEvidence(v.start,v.end,v.activation,lookup[v.start,v.end].f0_likelihood,v.voiced_probability)
                for v in interval_candidates(obs,candidate_cuts(obs,p.phonetic),4))
            # Native numerical pitch observations are not recomputed or altered.
            for v in edges:
                original=lookup[v.start,v.end]
                if not np.array_equal(v.activation,original.activation):
                    raise ValueError('Pitch pooling changed during presence-only migration')
            phrases.append(PhraseEvidence(p.offset_ms,obs,p.phonetic,edges))
        evidence=RecordingEvidence(old.duration_ms,old.source_sha256,tuple(phrases),old.observers)
        target=args.output/item['id']/'observations.npz';target.parent.mkdir(parents=True,exist_ok=True)
        save_evidence(evidence,target)
        records.append({'source':str(source),'destination':str(target),
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'destination_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'source_pcm_sha256':old.source_sha256,'numerical_pitch_unchanged':True})
        print(item['id'],'presence migrated; original unchanged',flush=True)
    (args.output/'migration.json').write_text(json.dumps({'policy':EVIDENCE_POLICY,'records':records},indent=2),encoding='utf8')


if __name__=='__main__':main()
