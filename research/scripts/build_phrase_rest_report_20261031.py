"""Build focused before/after evidence from the real recognition regression."""
from pathlib import Path
import base64,html,json,subprocess,wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'build/phrase_rest_fix_20261031'
out=ROOT/'output/phrase_rest_fix_20261031';out.mkdir(parents=True,exist_ok=True)
cards=[]
for label,title in [('lantingxu_p1_row_5','第一页第5行'),('lantingxu_p2_row_4','第二页第4行')]:
    players=[]
    for version,caption in [('before','修改前：两个假音'),('after','修改后：保留休止')]:
        data=json.loads((source/(label+'_'+version+'.json')).read_text(encoding='utf8'))
        rate=22050;samples=np.zeros(round(data['durationMs']*rate/1000)+1)
        for note in data['events']:
            if note['midi'] is None:continue
            n=max(1,round(note['gateMs']*rate/1000));t=np.arange(n)/rate
            phase=2*np.pi*440*2**((note['midi']-69)/12)*t
            signal=(np.sin(phase)+.3*np.sin(phase*2))*.22
            signal*=np.minimum(1,t/.025)*np.clip((n/rate-t)/.025,0,1)
            start=round(note['startMs']*rate/1000);length=min(n,len(samples)-start)
            if length>0:samples[start:start+length]+=signal[:length]
        wav=source/(label+'_'+version+'.wav')
        with wave.open(str(wav),'wb')as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate)
            f.writeframes(np.rint(np.clip(samples,-.8,.8)*32767).astype('<i2').tobytes())
        mp3=out/(label+'_'+version+'.mp3')
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-b:a','96k',str(mp3)],check=True)
        players.append(f'<p>{caption}</p><audio controls preload="metadata" src="data:audio/mpeg;base64,{base64.b64encode(mp3.read_bytes()).decode()}"></audio>')
    cards.append(f'<article><h2>{title}</h2>{"".join(players)}</article>')
report=json.loads((source/'regression.json').read_text(encoding='utf8'))
content='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>句间多余音修复核对</title><style>body{background:#091420;color:#e1eeed;font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif;margin:0}main{max-width:800px;padding:28px 20px 60px;margin:auto}h1{font-size:26px}h2{font-size:20px}article{background:#152d3c;padding:18px;border:1px solid #355465;border-radius:14px;margin:20px 0}audio{width:100%}.note{color:#efcd8e}a{color:#54e7cd}</style><main><h1>句间多余音：修复与试听对照</h1><p>2026-10-31 · 当前已确认的原因是休止符“0”碎裂后被错误补成“1”，不是逗号本身发音。</p><p>已移除“未知竖形残片补1”的规则；修复同一休止符两侧碎片的合并，同时保留紧邻的两个正常1。新裁图重新调用真实千问识别，未套用旧坐标的数字结果。</p><p>五页46行回归中，四个假音被去除、两个休止符恢复；另外两首样本的完整编译事件与修改前一致。五页首行103个参考符号继续通过，27项软件自动测试通过。</p><p class="note">以下是定位问题的局部候选对照，采用统一软件音色，不能当作FPGA实机试听或整谱已验收。其他复杂装饰音、反复、拍数冲突仍保留待核对状态。</p>'''+''.join(cards)+'''<p>正式测试入口：<a href="https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site/">声芯乐动网页版</a>。刷新页面后重新选谱识别；已经载入的旧结果不会在播放中被悄悄替换。</p></main></html>'''
(out/'句间多余音修复核对.html').write_text(content,encoding='utf8')
(out/'回归结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('focused_report_ready')
