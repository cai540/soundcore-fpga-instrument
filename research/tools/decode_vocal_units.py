"""Replay fixed native vocal-unit evidence without research or score imports."""
from dataclasses import asdict
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from soundcore_audio.vocal_units import VocalUnitConfig,pool_native_units,decode_vocal_units
from soundcore_audio.pipeline import export

POLICY='fixed-native-vocal-units-v1'


def load_units(path):
    with np.load(path,allow_pickle=False) as a:
        if str(a['policy'])!=POLICY:
            raise ValueError('Incompatible source-unit evidence policy')
        meta=json.loads(str(a['metadata']))
        if (meta.get('unit_source')!='automatic-source-audio'
                or not isinstance(meta.get('source_pcm_sha256'),str)
                or not meta['source_pcm_sha256']):
            raise ValueError('Source-only unit proposals with recording provenance required')
        cuts,raw,ranges=a['native_cuts'],a['native_activation'],a['ranges']
        activation=pool_native_units(cuts,raw,ranges)
        units=meta['units']
        if len(units)!=len(ranges) or not all(isinstance(u,str) and u for u in units):
            raise ValueError('Each source unit needs its own recognized label')
        return ranges.copy(),int(cuts[-1]),activation,a['physical'].copy(),a['centers'].copy(),meta


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    ranges,frames,activation,physical,centers,meta=load_units(args.evidence)
    config=VocalUnitConfig(**json.loads(args.config.read_text(encoding='utf8')))
    notes,key=decode_vocal_units(ranges,frames,activation,physical,centers,config)
    export(notes,args.output)
    details={'units':[{'recognized_unit':u,'notes':[asdict(n)]} for u,n in zip(meta['units'],notes)],
        'source_pcm_sha256':meta['source_pcm_sha256'],'config':asdict(config),'source_scale':key,
        'observer_metadata':meta,'evidence_sha256':hashlib.sha256(args.evidence.read_bytes()).hexdigest(),
        'policy':POLICY,'maximum_notes_per_unit':1,'postprocessing_corrections':0,
        'runtime_reference_score_or_lyrics_used':False,'recognized_lyrics_verified':False,
        'rhythm_accuracy_measured':False,'accepted':False,'integrated_in_apk_or_fpga':False}
    (args.output/'characters.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf8')
    print('saved',len(notes),'source-unit carriers',flush=True)


if __name__=='__main__':main()
