"""Pack verified source observers into a compact, independent replay cache.

Source text comes from an automatic ASR/aligner file. References are not read.
RMVPE is recomputed through its content-addressed observer cache. The second
F0 track must have a matching original 16k source digest in its manifest.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from soundcore_audio.audio import decode
from soundcore_audio.pipeline import load_evidence
from soundcore_audio.pitch import PitchObserver,interval_likelihood,scale_center
from soundcore_audio.vocal_units import validate_unit_ranges
from tools.decode_vocal_units import POLICY


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--native-evidence',type=Path,required=True)
    p.add_argument('--units',type=Path,required=True)
    p.add_argument('--secondary-f0',type=Path,required=True)
    p.add_argument('--secondary-manifest',type=Path,required=True)
    p.add_argument('--pitch-model',type=Path,required=True)
    p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    source=decode(args.source,44100)
    native=load_evidence(args.native_evidence)
    if (len(native.phrases)!=1 or native.phrases[0].offset_ms!=0
            or native.source_sha256!=hashlib.sha256(source.samples.tobytes()).hexdigest()):
        raise ValueError('The native evidence belongs to another source or spans multiple windows')
    units=json.loads(args.units.read_text(encoding='utf8'))
    if (units.get('known_lyrics_or_title_supplied') is not False
            or units['source_pcm_sha256']!=hashlib.sha256(decode(args.source,48000).samples.tobytes()).hexdigest()):
        raise ValueError('Source-only aligner evidence must match the recording')
    secondary_meta=json.loads(args.secondary_manifest.read_text(encoding='utf8'))
    if secondary_meta['source_pcm_sha256']!=hashlib.sha256(decode(args.source,16000).samples.tobytes()).hexdigest():
        raise ValueError('The independent F0 observer belongs to another recording')
    proposed=units['units']
    if not proposed or any(u['vowel_end_s']-u['vowel_start_s']<.04 for u in proposed):
        raise ValueError('Collapsed automatic vowels cannot be padded into notes')
    ranges=np.array([(round(u['vowel_start_s']*100),round((proposed[i+1]['vowel_start_s']
        if i+1<len(proposed) and proposed[i+1]['start_s']-u['end_s']<.12 else u['vowel_end_s'])*100))
        for i,u in enumerate(proposed)],int)
    observation=native.phrases[0].observation
    validate_unit_ranges(ranges,int(observation.cuts[-1]))
    model=PitchObserver(args.pitch_model,args.cache)
    f0,confidence=model.observe(source.samples,source.rate)
    with np.load(args.secondary_f0,allow_pickle=False) as q:
        ff,fc=q['f0'],q['confidence']
        if float(q['dt'])!=.01 or len(ff)<int(observation.cuts[-1]) or fc.shape!=ff.shape:
            raise ValueError('The independent F0 cache uses an incompatible source clock')
    physical=np.stack([interval_likelihood(f0,confidence,a,z) for a,z in ranges])
    centers=np.array([[scale_center(f0,confidence,a,z,.03),scale_center(ff,fc,a,z,.006)] for a,z in ranges],float)
    meta={'unit_source':'automatic-source-audio','source_pcm_sha256':native.source_sha256,
        'units':[u['character'] for u in proposed],'native_evidence_sha256':sha(args.native_evidence),
        'unit_observer_sha256':sha(args.units),'secondary_f0_sha256':sha(args.secondary_f0),
        'secondary_observer_metadata':secondary_meta,'pitch_model':model.metadata,
        'reference_score_or_lyrics_loaded':False,'source_duration_ms':source.duration_ms,
        'ownership':'vowel nucleus to next nucleus for adjacent units; source pause otherwise'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(args.output,policy=POLICY,metadata=json.dumps(meta,ensure_ascii=False),
        native_cuts=observation.cuts,native_activation=observation.pitch_activation,
        ranges=ranges,physical=physical,centers=centers)
    print('packed',len(ranges),'source-only units',flush=True)


if __name__=='__main__':main()
