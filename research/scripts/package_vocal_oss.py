"""Export auditable OSS auditions without editing model note decisions.

The named evaluation windows are playback bookmarks only. They are never
inputs to recognition. Full source-clock CSV/MIDI and raw traces are kept.
"""
from pathlib import Path
import csv, hashlib, json, shutil, subprocess, zipfile
import numpy as np
import mido
from transcribe_vocal_oss import write_notes, write_midi, render, encode_audio, device_fit
from evaluate_oss_vocals import read_notes

R=Path(__file__).resolve().parents[1]
B=R/'build/vocal_oss_20261029'
O=R/'output/vocal_oss_20261029'
CASES=[('zuguo','我和我的祖国',47090),('chilege','敕勒歌',30970),
       ('qiansixi','牵丝戏',23990),('lantingxu','兰亭序',490)]
MODELS=['rosvot','rosvot_checkpoint','basic','game_small','game_medium','game_medium_game_cli','consensus']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def segment(ns,start,end):
    return [{**n,'start_ms':max(start,n['start_ms'])-start,
             'duration_ms':min(end,n['start_ms']+n['duration_ms'])-max(start,n['start_ms'])}
            for n in ns if n['start_ms']<end and n['start_ms']+n['duration_ms']>start]

def validate(ns,ms):
    cursor=0
    for n in ns:
        assert cursor<=n['start_ms'] and n['duration_ms']>0 and 0<=n['midi']<=127
        cursor=n['start_ms']+n['duration_ms']
    assert cursor<=ms+10

def verify_midi(path,ns):
    mid=mido.MidiFile(path);clock=0.;events=[]
    for msg in mid:
        clock+=msg.time
        if msg.type in ('note_on','note_off'):events.append((round(clock*1000),msg.note,msg.type=='note_on' and msg.velocity>0))
    target=[]
    for n in ns:target.extend([(n['start_ms'],n['midi'],True),(n['start_ms']+n['duration_ms'],n['midi'],False)])
    assert events==target,(path,events[:5],target[:5])

def baseline_notes(name):
    ns=[]
    rows=json.loads((R/'build/vocal_final_phrases_20261029/audio_results.json').read_text(encoding='utf8'))
    for q in rows:
        if q['name']==name and q['window'].startswith('chunk_'):
            p=Path(q['new'])/'notes.csv'
            if p.exists():ns.extend([{**n,'start_ms':n['start_ms']+round(q['offset_seconds']*1000)} for n in read_notes(p)])
    return sorted(ns,key=lambda n:n['start_ms'])

def main():
    O.mkdir(parents=True,exist_ok=True)
    index=[];media=[]
    for name,title,bookmark in CASES:
        d=O/name;d.mkdir(exist_ok=True)
        source=B/'game_medium'/name/'full'
        info=json.loads((source/'result.json').read_text(encoding='utf8'))
        pcm=np.fromfile(info['input_file'],dtype='<f4')
        ms=info['source_ms'];pcm=pcm[:ms*16]
        ns=read_notes(source/'notes.csv');old=baseline_notes(name)
        validate(ns,ms);validate(old,ms)
        write_notes(ns,d/'完整原时间轴.csv');write_midi(ns,d/'完整原时间轴.mid');verify_midi(d/'完整原时间轴.mid',ns)
        write_notes(old,d/'旧0.9原时间轴.csv')
        shutil.copy2(source/'trace.json',d/'模型原始轨迹.json')
        synth=render(ns,ms);old_synth=render(old,ms)
        # A full-clock comparison exposes introductory false positives too.
        media.append(encode_audio(np.column_stack([pcm,synth]),d/'全文件对照_左人声右识别.mp3'))
        # Known evaluation bookmark is only a preview trim; no internal rests removed.
        final=min(ms,max(n['start_ms']+n['duration_ms'] for n in ns))
        audition=segment(ns,bookmark,final)
        write_midi(audition,d/'人声段试听.mid');verify_midi(d/'人声段试听.mid',audition)
        media.append(encode_audio(synth[bookmark*16:final*16],d/'人声段完整试听.mp3'))
        media.append(encode_audio(np.column_stack([old_synth,synth])[bookmark*16:final*16],d/'新旧整段对照_左旧右新.mp3'))
        first_end=min(ms,bookmark+40000)
        media.append(encode_audio(np.column_stack([pcm,synth])[bookmark*16:first_end*16],d/'前40秒_左人声右识别.mp3'))
        if name=='zuguo':
            a=bookmark+40000;z=min(ms,a+40000)
            media.append(encode_audio(np.column_stack([pcm,synth])[a*16:z*16],d/'第41至80秒_左人声右识别.mp3'))
        row={**info,'title':title,'preview_source_start_ms':bookmark,'preview_source_end_ms':final,
             'preview_trim_is_evaluation_bookmark_not_automatic_voice_detection':True,
             'note_pitch_range':[min(n['midi'] for n in ns),max(n['midi'] for n in ns)],
             'original_first_event_ms':ns[0]['start_ms'],'device':device_fit(ns,ms),
             'boundary_threshold':.2,'postprocessing_pitch_or_duration_edits':False,
             'not_fpga_timbre':True,'not_android_release':True,'human_listening_accepted':False}
        (d/'结果说明.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8');index.append(row)
        print('exported',title,len(ns),flush=True)
    # Keep all competing event lists so selection/rejections can be audited.
    for model in MODELS:
        for name,title,_ in CASES:
            src=B/model/name/'full'
            dst=O/'comparison_data'/model/name;dst.mkdir(parents=True,exist_ok=True)
            for leaf in ['notes.csv','result.json']:
                if (src/leaf).exists():shutil.copy2(src/leaf,dst/leaf)
    for leaf in ['offline_diagnostics.json','real_inference_sanity.json','baseline_sha256.json']:
        shutil.copy2(B/leaf,O/leaf)
    srcdir=O/'source';srcdir.mkdir(exist_ok=True)
    scripts=['game_vocal_engine.py','oss_vocal_engine.py','oss_vocal_postprocess.py','oss_vocal_consensus.py',
             'benchmark_oss_vocals.py','benchmark_vocal_consensus.py','evaluate_oss_vocals.py',
             'transcribe_vocal_oss.py','package_vocal_oss.py','test_oss_vocal_adapter.py','verify_oss_inference.py',
             'run_oss_transcription.ps1']
    for leaf in scripts:shutil.copy2(R/'scripts'/leaf,srcdir/leaf)
    repos=[]
    for repo,url in [('GAME','https://github.com/openvpi/GAME'),('ROSVOT','https://github.com/RickyL-2000/ROSVOT'),('basic-pitch','https://github.com/spotify/basic-pitch')]:
        rev=subprocess.check_output(['git','-C',str(B/repo),'rev-parse','HEAD'],text=True).strip()
        dst=O/'licenses';dst.mkdir(exist_ok=True);shutil.copy2(B/repo/'LICENSE',dst/f'{repo}_LICENSE')
        repos.append({'repo':url,'commit':rev,'license_sha256':sha(B/repo/'LICENSE')})
    baseline=json.loads((B/'baseline_sha256.json').read_text(encoding='utf8'))
    changed=[p for p,h in baseline.items() if sha(R/p)!=h]
    assert not changed,changed
    (O/'validation.json').write_text(json.dumps({'media_count':len(media),'media':media,
        'all_exported_midi_exact_ms_roundtrip':True,'all_note_clocks_valid':True,
        'production_files_hash_checked':len(baseline),'production_files_changed':changed,
        'phone_or_fpga_tested':False,'human_listening_accepted':False},ensure_ascii=False,indent=2),encoding='utf8')
    (O/'provenance.json').write_text(json.dumps({'candidate':'GAME-1.0.3-medium-onnx .2,8steps,zh,CPU',
         'models':repos,'cases':index,'pretrained_models_not_bundled':True},ensure_ascii=False,indent=2),encoding='utf8')
    (O/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf8')
    print('saved',O,flush=True)

if __name__=='__main__':main()
