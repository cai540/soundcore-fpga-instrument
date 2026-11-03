"""Package source-only runtime replay, then independently score and audition."""
from pathlib import Path
from dataclasses import asdict
import csv,hashlib,html,json,shutil,subprocess,sys,zipfile
import numpy as np
from soundcore_audio.audio import decode
from soundcore_audio.vocal_units import VocalUnitConfig
from tools.preview_transcriptions import render,encode,verify_midi
from evaluation.transcription.character_metrics import compare_groups,gate

OUT=Path('output/vocal_units40_20261030')
TITLES={'zuguo':'我和我的祖国','qiansixi':'牵丝戏','chilege':'敕勒歌'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read_notes(path):
    with path.open(encoding='utf8',newline='') as f:return [{k:int(v) for k,v in row.items()} for row in csv.DictReader(f)]

def main():
    OUT.mkdir(exist_ok=True)
    config=asdict(VocalUnitConfig())
    (OUT/'config.json').write_text(json.dumps(config,indent=2),encoding='utf8')
    cases=json.loads(Path('build/vocal_40s_phrase_20261030/inputs.json').read_text(encoding='utf8'))['cases']
    # The runtime subprocess below does not receive any reference path.
    for case in cases:
        ident=case['id'];target=OUT/ident;target.mkdir(exist_ok=True)
        shutil.copyfile(Path('build/tifa_20261030/replay_cache')/ident/'evidence.npz',target/'source_unit_evidence.npz')
        subprocess.run([sys.executable,'-m','tools.decode_vocal_units',
            '--evidence',str(target/'source_unit_evidence.npz'),'--config',str(OUT/'config.json'),
            '--output',str(target)],check=True)
        research=Path('build/tifa_20261030/fixed_source/0.5_0.5')/ident
        if (target/'notes.csv').read_bytes()!=(research/'notes.csv').read_bytes():
            raise ValueError('Clean runtime and research candidate differ')
    old_ref=json.loads(Path('evaluation/transcription/character_reference40.json').read_text(encoding='utf8'))
    ref=json.loads(Path('evaluation/transcription/character_reference40_audited.json').read_text(encoding='utf8'))
    references={c['id']:[u for p in c['phrases'] for u in p['units']] for c in ref['cases']}
    old_references={c['id']:[u for p in c['phrases'] for u in p['units']] for c in old_ref['cases']}
    reports=[];cards=[]
    for case in cases:
        ident=case['id'];target=OUT/ident;details=json.loads((target/'characters.json').read_text(encoding='utf8'))
        observed=[[n['midi'] for n in u['notes']] for u in details['units']]
        evaluation=compare_groups(references[ident],observed);evaluation['id']=ident
        old_evaluation=compare_groups(old_references[ident],observed)
        base=Path('output/vocal_carriers40_20261030')/ident
        previous=json.loads((base/'characters.json').read_text(encoding='utf8'))['units']
        baseline=compare_groups(references[ident],[[n['midi'] for n in u['notes']] for u in previous])
        notes=read_notes(target/'notes.csv');old_notes=read_notes(base/'notes.csv')
        verify_midi(notes,target/'source_clock.mid')
        pitch_changes=sum(a['midi']!=b['midi'] for a,b in zip(notes,old_notes))
        timing_changes=sum(a['start_ms']!=b['start_ms'] or a['duration_ms']!=b['duration_ms'] for a,b in zip(notes,old_notes))
        if ident in ('qiansixi','chilege') and pitch_changes:raise ValueError('Previously accepted pitch path changed')
        wave=decode(case['clip'],16000).samples
        if len(wave)!=640000:raise ValueError('Frozen source window changed')
        melody=render(notes,len(wave));gain=min(1.,.85/max(float(abs(wave).max()),1e-9))
        media=[encode(melody,target/'melody_40s.mp3'),encode(np.column_stack([wave*gain,melody]),target/'comparison_40s.mp3')]
        row={'id':ident,'title':TITLES[ident],'source_offset_s':case['start_s'],'duration_s':40,
            'score_pitch_and_ownership':evaluation,'previous_annotation_metric':old_evaluation,
            'baseline_under_same_audited_reference':baseline,'pitch_changes':pitch_changes,
            'units_with_timing_changes':timing_changes,'media':media,'source_clip_pcm_sha256':case['clip_pcm_sha256'],
            'source_clock_midi_sha256':sha(target/'source_clock.mid'),'notes_csv_sha256':sha(target/'notes.csv'),
            'runtime_config':config,'reference_entered_runtime':False,'human_listening_verified':False,
            'rhythm_accuracy_measured':False,'whole_song_accuracy_verified':False}
        (target/'evaluation.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8');reports.append(row)
        percent=evaluation['strict_character_melody_consistency']*100
        cards.append(f'''<article><h2>{TITLES[ident]}</h2><p class="score">{evaluation['correct']}/{evaluation['reference_characters']} · {percent:.0f}%</p>
<p>40秒简化主音核对 · 含正确八度与字的归属。起止调整{timing_changes}个单位，音高改动{pitch_changes}处。</p>
<label>新候选旋律</label><audio controls preload="metadata" src="{ident}/melody_40s.mp3"></audio>
<label>原人声在左，识别旋律在右</label><audio controls preload="metadata" src="{ident}/comparison_40s.mp3"></audio>
<p>0:00对应原人声{case['start_s']}秒。保持固定40秒窗口与内部停顿。</p>
<p><a href="{ident}/source_clock.mid">MIDI</a> · <a href="{ident}/notes.csv">音符起止</a> · <a href="{ident}/evaluation.json">逐字核对</a></p></article>''')
    runtime_files=[*Path('soundcore_audio').glob('*.py'),Path('tools/decode_vocal_units.py'),Path('tools/pack_vocal_unit_cache.py'),Path('tools/decode_vocal_carriers.py')]
    snapshot=OUT/'source_review'
    for p in runtime_files+[Path('pyproject.toml'),Path('soundcore_audio/README.md'),Path('evaluation/transcription/character_metrics.py'),Path('tests/test_articulation.py'),Path('tests/test_articulation_cli.py'),Path('tests/test_vocal_units.py')]:
        dest=snapshot/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    reference_dir=OUT/'evaluation_reference';reference_dir.mkdir(exist_ok=True)
    for name in ['character_reference40.json','character_reference40_audited.json']:
        shutil.copyfile(Path('evaluation/transcription')/name,reference_dir/name)
    report={'config':config,'cases':reports,'annotation_audit':ref['annotation_audit'],
        'runtime_source_sha256':{str(p):sha(p) for p in runtime_files},
        'numerical_clip_gate':gate([r['score_pitch_and_ownership'] for r in reports]),
        'parameter_selection_used_these_development_clips':True,'heldout_accuracy_claimed':False,
        'known_remaining_issue':'Zuguo 都流出一首赞歌 的 一: predicted MIDI60, score MIDI72.',
        'rhythm_accuracy_measured':False,'whole_song_accuracy_claimed':False,'human_listening_verified':False,
        'apk_updated':False,'fpga_programmed':False,'musical_acceptance_passed':False}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>三首40秒 · 固定观测主音试听</title><style>
body{margin:44px auto;padding:0 24px;max-width:1160px;background:#091720;color:#e8f2f4;font:15px/1.8 "Microsoft YaHei",sans-serif}h1{font-size:32px}p{color:#a9bec8}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:22px}article{background:#142b37;border:1px solid #315463;border-radius:18px;padding:24px}h2{font-size:24px}.score{color:#55ddc3;font-size:26px;margin:10px 0}label{display:block;margin-top:22px}audio{width:100%;height:42px}a{color:#59dcbf}.notice{padding:18px;background:#372e20;border:1px solid #685237;border-radius:12px;color:#e7ca94}.audit{padding:18px;background:#10242e;border-radius:12px;margin:18px 0}footer{margin:26px 0;color:#a9bec8}</style>
<h1>三首40秒 · 固定原始观测的逐字主音</h1><p>同一套算法与参数，从源人声自动识字和定位。每个发音单位保留一个主音，音高不从曲名、简谱或旧MIDI读取。参考音是统一正弦音，并非FPGA实录。</p>
<div class="notice">数值是这三个开发片段的“允许简化主音＋字的归属”核对，不能代表整曲、泛化或节奏准确率。试听尚未人工验收。祖国仍有一处已知八度错误：一首赞歌的“一”低一八度。没有烧录，没有更新APK。</div>
<div class="audit">校对表审计：原谱“无论我走到哪里”的“我”是6，“走”包含5→4；旧表把部分音归错字。旧表、旧结果、修改记录均保留。按同一修正标准，祖国旧版45/50，新版49/50；若机械沿用旧表，新版为47/50。字内允许的简化不等于逐个还原全部转音。</div><main>'''+''.join(cards)+'''</main><footer>
<a href="三首40秒试听与MIDI.zip">全部试听与MIDI</a> · <a href="report.json">完整核对记录</a> · <a href="README.txt">复算说明</a></footer><script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    (OUT/'试听与核对.html').write_text(page,encoding='utf8')
    (OUT/'README.txt').write_text('''实验候选，未烧录、未更新APK；非整曲或通用准确率验收。
新核心不导入build研究目录或evaluation参考谱。source_review包含独立复算源码，先安装numpy、scipy、mido。
在source_review目录执行：
python -m tools.decode_vocal_units --evidence ../zuguo/source_unit_evidence.npz --config ../config.json --output replay
缓存内容是原模型固定观测、自动字界和F0测量，不是按曲名索引的音符答案。
从原音频重新生成观察器仍需要本地Qwen ASR、TIFA、GAME、RMVPE和FCPE模型，本包不包含大模型权重。
FCPE作者DDSP模型仅用于本地研究，未打包进App。本次没有修改手机端或固件。
report.json同时保留旧校对表与经原简谱审计后的结果。数值门槛通过不等于节奏、整曲或听感已验收。
''',encoding='utf8')
    with zipfile.ZipFile(OUT/'三首40秒试听与MIDI.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file() and p.suffix in ('.mp3','.mid','.csv','.json','.html','.txt','.npz','.py','.toml'):
                z.write(p,p.relative_to(OUT))
    print(OUT/'试听与核对.html',flush=True)

if __name__=='__main__':main()
