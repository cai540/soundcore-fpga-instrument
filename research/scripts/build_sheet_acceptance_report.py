from pathlib import Path
import json,numpy as np,wave,subprocess,shutil,base64,html
root=Path('D:/FPGA/Projects/soundcore_2026');source=root/'build/sheet_acceptance_20261031';out=root/'output/sheet_acceptance_20261031';out.mkdir(parents=True,exist_ok=True)
labels={'zuguo':'我和我的祖国','chilege':'敕勒歌','lantingxu':'兰亭序'};previews=[]
for name,title in labels.items():
 data=json.loads((source/'final'/f'{name}_preview.json').read_text(encoding='utf8'));rate=22050;samples=np.zeros(round(data['durationMs']*rate/1000)+1)
 for note in data['events']:
  if note['midi'] is None:continue
  n=max(1,round(note['gateMs']*rate/1000));t=np.arange(n)/rate;freq=440*2**((note['midi']-69)/12)
  vibrato=(np.clip((t-.15)/.3,0,1)*np.sin(2*np.pi*5*t)*(.006 if name=='chilege' else .0025));phase=2*np.pi*np.cumsum(freq*(1+vibrato))/rate
  harmonics=[1,.56,.31,.19,.1,.07] if name=='chilege' else [1,.5,.22,.14,.08,.04]
  signal=sum(weight*np.sin((i+1)*phase)for i,weight in enumerate(harmonics)if(i+1)*freq<rate/2)
  env=np.minimum(1,t/.025)*np.clip((n/rate-t)/.025,0,1);signal*=env*.12
  start=round(note['startMs']*rate/1000);length=min(n,len(samples)-start)
  if length>0:samples[start:start+length]+=signal[:length]
 peak=float(np.max(np.abs(samples)));samples*=min(1,.4/max(peak,1e-6))
 wav=source/'final'/f'{name}_40s.wav'
 with wave.open(str(wav),'wb')as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(np.rint(samples*32767).astype('<i2').tobytes())
 target=out/f'{title}_AI图片识谱_40s_待核对.mp3';subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-b:a','96k',str(target)],check=True)
 previews.append(f'<article><h3>{html.escape(title)} · 前40秒待核对试听</h3><audio controls preload="none" src="data:audio/mpeg;base64,{base64.b64encode(target.read_bytes()).decode()}"></audio></article>')
comparison=json.loads((source/'manual-comparison.json').read_text(encoding='utf8'));summary=json.loads((source/'final/summary.json').read_text(encoding='utf8'))
rows=''.join(f'<tr><td>{labels.get(s["name"],s["name"])}</td><td>{s["pages"]}</td><td>{s["rows"]}</td><td>{s["notes"]}</td><td>待核对 {s["issues"]} 处</td></tr>'for s in summary)
refrows=''.join(f'<tr><td>{html.escape(s["name"])}</td><td>{s["expected"]}</td><td>{s["pitches"]}/{s["expected"]}</td><td>{s["durations"]}/{s["expected"]}</td></tr>'for s in comparison['samples'])
content=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>简谱样本检测与试听 · 2026-10-31</title><style>body{{font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif;background:#091420;color:#e1eeed;margin:0}}main{{max-width:860px;margin:auto;padding:32px 20px 70px}}h1{{font-size:27px}}h2{{font-size:21px;margin-top:35px}}h3{{font-size:17px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border:1px solid #355465;text-align:left;padding:10px}}.notice{{background:#44321c;border:1px solid #aa8554;border-radius:12px;padding:18px;color:#f1d299}}article{{padding:18px;background:#152d3c;border-radius:12px;margin:16px 0}}audio{{width:100%}}a{{color:#54e7cd}}small{{color:#9bb1b8}}code{{word-break:break-all}}</style><main><h1>五页简谱 · 样本检测与试听</h1><p>2026年10月31日 · 原图保全、逐符号读取、人工参考回归</p><div class="notice"><strong>当前结论：局部回归通过，整曲尚未验收。</strong><br>五页首行共103个音符及休止符，数字、八度与时值均与人工阅读参考一致。这个结果来自开发回归集，不能当作整首歌曲或新曲谱的准确率。</div><h2>首行人工参考核对</h2><table><tr><th>谱页</th><th>符号数</th><th>音高 / 休止</th><th>时值</th></tr>{refrows}</table><p>参考直接逐个阅读所附图片，不调用原来手工制作的歌曲模型。修改的是通用像素与符号规则，没有按歌名补音高。复用云端数字结果前，程序逐一确认裁图坐标完全相同。</p><h2>整谱读取状态</h2><table><tr><th>曲目</th><th>页数</th><th>谱行</th><th>发声音符事件</th><th>状态</th></tr>{rows}</table><p>“待核对”包括拍数冲突、装饰音残片、反复或局部拍号未知；不是已经确定有同等数量的错音。结构结果未确认时按谱面顺序生成候选，不自动执行存疑反复。未对整曲每个音建立独立人工标注，不能给出整曲正确率。</p><h2>40秒实际候选试听</h2><p>音符来自这次图片识别与统一编译。使用软件合成近似音色，含谱面前奏；与FPGA实机有差异。尚有待核对位置，不能将以下音频称为最终演示版。</p>{''.join(previews)}<h2>本次修正</h2><ul><li>上点、下点、右附点和减时线分开处理，附点不再为了凑拍而删除。</li><li>漏读数字保留编号，不再导致后续全部错位；修复轻灰小节线和把细体1当小节线的问题。</li><li>修复紧贴数字的上点漏读、歌词小笔画误作低音点。</li><li>6/8与9/8混合拍号分别核对。原谱存在的时值矛盾会保留待核对。</li><li>播放采用音频时钟；自然换气仅收短发音尾部，不改起音位置或整段节拍。</li><li>支持多页顺序、完成行缓存、取消、原图定位、音级/八度/时值编辑。</li></ul><h2>限制与失败证据</h2><p>百炼部分整页结构请求返回 <code>data_inspection_failed</code>，另有网络中断。未把它们报告为识谱成功；内容检查拒绝与网络超时分别呈现，已完成的数字结果可以保留。复杂装饰音、反复及跨页结构仍需复核。</p><p>《我和我的祖国》首行第二小节可见“1.”后接低音5，按可见记号仅合2.5个四分音符拍，不满足6/8或9/8。程序保留原图记号，并未擅自增删附点。</p><h2>软件验证</h2><p>24项自动测试通过，TypeScript检查通过；手机390px宽度完成选图、原图定位、音符编辑、试听和停止的界面回放，无横向溢出。界面回放使用明确标记的参考响应，与真实千问识别测试分开记录。未修改APK或烧录FPGA。</p><p>正式测试入口：<a href="https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site/">声芯乐动手机体验版</a>。发布状态另见交付记录。</p><small>本HTML内嵌试听音频，可单独打开。原图和API凭据未嵌入本页。</small></main></html>'''
(out/'样本检测与试听.html').write_text(content,encoding='utf8')
shutil.copyfile(source/'manual-comparison.json',out/'首行人工核对结果.json');shutil.copyfile(source/'final/summary.json',out/'整谱读取状态.json')
print('previews_and_report_created',out)
