"""Render existing note outputs for audition; never infer or edit the notes.

Titles and source filenames label the audition page only. All notes, including
mistakes, rests and source-clock offsets, come unchanged from each notes.csv.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import html
import json
import subprocess
import zipfile

import numpy as np
import mido


RATE = 16000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(notes, samples):
    """Same neutral 12/18 ms sine envelope for every song, no pitch folding."""
    result = np.zeros(samples, np.float32)
    phase = 0.
    cursor = 0
    for note in notes:
        start, duration, pitch = (note[k] for k in ('start_ms', 'duration_ms', 'midi'))
        if start < cursor or duration <= 0 or not 1 <= pitch <= 127:
            raise ValueError('Invalid or overlapping note input')
        cursor = start + duration
        a, z = round(start * RATE / 1000), min(samples, round(cursor * RATE / 1000))
        if a >= samples or z <= a:
            raise ValueError('Note outside decoded source')
        t = np.arange(z - a) / RATE
        omega = 2 * np.pi * 440 * 2 ** ((pitch - 69) / 12)
        envelope = np.minimum(1, t / .012) * np.minimum(1, (z - a - np.arange(z - a)) / RATE / .018)
        result[a:z] = np.sin(phase + omega * t) * envelope * .22
        phase = (phase + omega * (z - a) / RATE) % (2 * np.pi)
    return result


def encode(pcm, path):
    if not np.isfinite(pcm).all() or np.max(np.abs(pcm)) >= 1:
        raise ValueError('Nonfinite or clipping preview')
    channels = 1 if pcm.ndim == 1 else pcm.shape[1]
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(RATE),
        '-ac', str(channels), '-i', 'pipe:0', '-c:a', 'libmp3lame', '-q:a', '2', str(path)],
        input=pcm.astype('<f4').tobytes(), check=True)
    decoded = np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
        '-f', 'f32le', '-ar', str(RATE), '-ac', str(channels), '-']), dtype='<f4')
    if len(decoded) != pcm.size or not np.isfinite(decoded).all() or abs(decoded).max() >= .999:
        raise ValueError('Encoded audio failed duration or clipping verification')
    return {'file': path.name, 'channels': channels, 'duration_s': len(pcm) / RATE,
            'peak_decoded': float(abs(decoded).max()), 'sha256': sha(path)}


def verify_midi(notes, path):
    events, clock = [], 0.
    for event in mido.MidiFile(path):
        clock += event.time
        if event.type in ('note_on', 'note_off'):
            events.append((round(clock * 1000), event.note,
                           event.type == 'note_on' and event.velocity > 0))
    expected = []
    for n in notes:
        expected.extend([(n['start_ms'], n['midi'], True),
                         (n['start_ms'] + n['duration_ms'], n['midi'], False)])
    if events != expected:
        raise ValueError('MIDI and CSV notes differ')


def make_preview(case, root):
    directory = root / case['id']
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf8'))
    with (directory / 'notes.csv').open(encoding='utf8', newline='') as stream:
        notes = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(stream)]
    if not notes or manifest['notes'] != len(notes):
        raise ValueError('Missing or inconsistent transcription')
    verify_midi(notes, directory / 'source_clock.mid')
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', case['audio'],
        '-ar', str(RATE), '-ac', '1', '-f', 'f32le', '-'])
    source = np.frombuffer(raw, dtype='<f4').copy()
    if abs(len(source) / RATE * 1000 - manifest['duration_ms']) > 1:
        raise ValueError('Source duration differs from transcription')
    melody = render(notes, len(source))
    source_gain = min(1., .85 / max(float(abs(source).max()), 1e-9))
    stereo = np.column_stack([source * source_gain, melody])
    # Only empty outside margins are omitted from the convenience players.
    # Internal pauses, note pitches and durations remain untouched.
    start_ms = max(0, notes[0]['start_ms'] - 250)
    end_ms = min(manifest['duration_ms'], notes[-1]['start_ms'] + notes[-1]['duration_ms'] + 500)
    a, z = round(start_ms * RATE / 1000), min(len(source), round(end_ms * RATE / 1000))
    media = [encode(melody[a:z], directory / 'melody.mp3'),
             encode(stereo[a:z], directory / 'source_left_melody_right.mp3'),
             encode(melody, directory / 'melody_source_clock.mp3')]
    report = {**case, 'source_file_sha256': sha(Path(case['audio'])),
        'source_duration_ms': manifest['duration_ms'], 'note_count': len(notes),
        'preview_start_ms_on_source': start_ms, 'preview_end_ms_on_source': end_ms,
        'source_gain_for_comparison': source_gain, 'melody_peak': float(abs(melody).max()),
        'reference_timbre': 'neutral sine, 12ms attack and 18ms release, amplitude 0.22',
        'notes_edited': False, 'internal_silence_removed': False, 'pitch_shift': 0,
        'time_stretch': 1, 'midi_csv_exact_match': True,
        'notes_csv_sha256': sha(directory / 'notes.csv'),
        'source_clock_midi_sha256': sha(directory / 'source_clock.mid'),
        'manifest_sha256': sha(directory / 'manifest.json'), 'media': media,
        'runtime_config': manifest['config'], 'runtime_source_sha256': manifest['source_sha256'],
        'whole_song_accuracy_verified': False}
    (directory / 'preview.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    return report


def write_page(reports, root):
    cards = []
    for r in reports:
        folder, title = html.escape(r['id']), html.escape(r['title'])
        duration = (r['preview_end_ms_on_source'] - r['preview_start_ms_on_source']) / 1000
        cards.append(f'''<article><p class="eyebrow">FULL RECORDING · {duration/60:.2f} MIN</p>
<h2>{title}</h2><p class="meta">{r['note_count']} 个识别音符 · 原录音 {r['source_duration_ms']/1000:.2f} 秒</p>
<label>识别旋律 · 整曲结果</label><audio controls preload="metadata" src="{folder}/melody.mp3"></audio>
<label>原声对照 · 左原声 / 右旋律（建议戴耳机）</label>
<audio controls preload="metadata" src="{folder}/source_left_melody_right.mp3"></audio>
<p class="meta">播放器 0:00 对应原录音 {r['preview_start_ms_on_source']/1000:.2f} 秒。仅省略首尾无音符空白；中间停顿完整保留。</p>
<div class="links"><a href="{folder}/source_clock.mid" download>原时间轴 MIDI</a>
<a href="{folder}/notes.csv" download>音符数据</a><a href="{folder}/melody_source_clock.mp3">保留原始起点的试听</a></div></article>''')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>四首人声 · 新核心整曲试听</title><style>
:root{color-scheme:dark;font-family:Segoe UI,Microsoft YaHei,sans-serif;background:#081520;color:#eaf4f5}
body{margin:0 auto;max-width:1120px;padding:50px 24px}h1{font-size:clamp(28px,5vw,44px);margin:12px 0}
.eyebrow{color:#50dbc7;letter-spacing:2px;font-size:12px}.lead{max-width:800px;color:#9fb6c2;line-height:1.8}
.notice{padding:16px 20px;background:#352d24;border:1px solid #6b5132;border-radius:12px;color:#e4c08a;line-height:1.7;margin:24px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,430px),1fr));gap:20px}
article{padding:26px;background:#132935;border:1px solid #294b59;border-radius:20px}h2{font-size:27px;margin:10px 0}
.meta{color:#8fa8b5;font-size:13px;line-height:1.7}label{display:block;margin:23px 0 9px;font-size:14px}audio{width:100%;height:44px}
.links{display:flex;gap:18px;flex-wrap:wrap;margin-top:22px}a{color:#59dfcc;text-decoration:none;font-size:13px}a:hover{text-decoration:underline}
footer{margin:30px 0;color:#8fa8b5;font-size:13px;line-height:1.8}</style>
<p class="eyebrow">SOUNDCORE / AUDIO LAB / 2026.10.30</p><h1>四首人声 · 新核心整曲试听</h1>
<p class="lead">从四份原始人声录音完整重新识别。使用相同的冻结参数、相同参考音色，直接播放算法产生的音高和时值；未逐曲改谱、移调或变速。</p>
<div class="notice">这是实验试听，不是已验收曲库或 FPGA 实录。已有片段检查仍暴露兰亭序的错音和多余音符；整曲准确率尚未达到可确认 90% 的程度。</div><main class="grid">'''
    page += '\n'.join(cards) + '''</main><footer>合成参考音为正弦音，用于判断旋律与节奏。对照版保留同一时间轴，左声道原人声，右声道识别旋律。<br>
<a href="四首整曲试听与MIDI.zip" download>下载全部试听与 MIDI</a> · <a href="suite_manifest.json">生成与音频校验记录</a></footer>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    (root / '整曲试听.html').write_text(page, encoding='utf8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = []
    for case in json.loads(args.suite.read_text(encoding='utf8')):
        reports.append(make_preview(case, args.output))
        print('rendered and verified', case['id'], flush=True)
    if not reports or any(r['runtime_config'] != reports[0]['runtime_config'] or
                          r['runtime_source_sha256'] != reports[0]['runtime_source_sha256']
                          for r in reports):
        raise ValueError('The suite must use identical frozen code and configuration')
    (args.output / 'suite_manifest.json').write_text(json.dumps({
        'preview_generator_sha256': sha(Path(__file__)), 'reports': reports,
        'same_configuration_for_all_songs': True, 'accepted': False}, ensure_ascii=False, indent=2), encoding='utf8')
    write_page(reports, args.output)
    with zipfile.ZipFile(args.output / '四首整曲试听与MIDI.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(args.output.rglob('*')):
            if p.is_file() and p.suffix in ('.mp3', '.mid', '.csv', '.json', '.html'):
                archive.write(p, p.relative_to(args.output))
    print(args.output / '整曲试听.html', flush=True)


if __name__ == '__main__':
    main()
