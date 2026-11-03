"""Gate and package the complete reed candidate. No device or programmer access."""
from pathlib import Path
import json,re,hashlib,shutil,stat,zipfile,xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import markdown
R=Path(__file__).resolve().parents[1];B=R/'build/harmonica_refinement_20261102';BASE=R/'build/acceptance_20261102';O=R/'output/harmonica_refinement_20261102';N='soundcore_speaker_omr_60k'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cp(p,q):
    q.parent.mkdir(parents=True,exist_ok=True)
    if q.exists():q.chmod(stat.S_IREAD|stat.S_IWRITE)
    shutil.copy2(p,q)
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf8')
def pinout(path):
    s=BeautifulSoup(path.read_text(),'html.parser');a=s.find(attrs={'name':'Pinout_by_Port_Name'});table=a.find_next('table')if a else None
    if table is None:
        text=path.read_text();start=text.index('name="Pinout_by_Port_Name"');s=BeautifulSoup(text[start:text.index('</table>',start)+8],'html.parser');table=s.find('table')or s
    result={}
    for row in table.find_all('tr'):
        cells=[c.get_text(' ',strip=True)for c in row.find_all('td')]
        if len(cells)>=5 and cells[0]!='Port Name':result[cells[0]]=cells[2].split('/')[0]
    assert result;return result
def main():
    fs=B/'impl/pnr'/(N+'.fs');assert fs.exists()and fs.stat().st_mtime>=(B/'build.tcl').stat().st_mtime
    assert re.search(r'//UserCode:\s*0x0000a6c4\b',fs.read_text(),re.I)
    assert 'Bitstream generation completed'in(B/'build.log').read_text('utf8')
    timing_path=B/'impl/pnr'/(N+'_tr_content.html');assert timing_path.stat().st_mtime>=(B/'build.tcl').stat().st_mtime
    t=BeautifulSoup(timing_path.read_text(),'html.parser').get_text(' ',strip=True)
    violations={k:int(re.search(r'Numbers of '+k+r' Violated Endpoints (\d+)',t)[1])for k in('Setup','Hold')};assert sum(violations.values())==0
    fmax=float(re.search(r'12\.288\(MHz\) ([\d.]+)\(MHz\)',t)[1]);assert fmax>12.288
    resources={};text=(B/'impl/pnr'/(N+'.rpt.txt')).read_text()
    for key in('Logic','CLS','Register','BSRAM','DSP'):
        m=re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/(\d+)',text,re.M);assert m,key
        resources[key]=dict(used=float(m[1]),available=int(m[2]));assert float(m[1])<=int(m[2])
    pins=pinout(B/'impl/pnr'/(N+'.pin.html'));assert pins==pinout(BASE/'impl/pnr'/(N+'.pin.html'))
    frozen=json.loads((B/'frozen_inputs.json').read_text());assert all(sha(B/'src'/p)==h for p,h in frozen.items())
    # Audition modules were compiled from working sources. Verify the exact
    # production equivalents, including the generator assets, after rebasing.
    root_audio={}
    for name in['expressive_texture.v','poly_synth32_tm.v','instrument_attack.vh','synth_voice.v']:
        p=R/'rtl'/name;s=p.read_text('utf8').replace('"rtl/instrument_attack.vh"','"src/rtl/instrument_attack.vh"')
        for literal in re.findall(r'"(D:/FPGA/Projects/soundcore_2026/[^"\n]+)"',s):
            target=B/'src/assets'/(hashlib.sha256(literal.encode()).hexdigest()[:8]+'_'+Path(literal).name)
            s=s.replace(literal,target.as_posix());assert target.exists()
        assert s==(B/'src/rtl'/name).read_text('utf8'),name
        root_audio['rtl/'+name]=sha(p)
    for name in['regression_results.json','capture_results.json']:
        assert all(x['passed']for x in json.loads((B/name).read_text()))
    assert json.loads((B/'math_validation.json').read_text())['passed']
    voices=json.loads((B/'voices32_results.json').read_text());assert voices['voices']==32 and voices['max_frame_cycles']<256
    latency=json.loads((B/'latency/summary.json').read_text());assert latency['max_step_to_abs64_i2s_ms']<5
    audio_path=B/'audio_validation.json';assert audio_path.stat().st_mtime>=(B/'build.tcl').stat().st_mtime
    audio=json.loads(audio_path.read_text('utf8'));assert audio['actual_rtl_capture']and len(audio['previews'])==4
    assert audio['frozen_input_ledger_sha256']==sha(B/'frozen_inputs.json')
    assert all(sha(B/p)==h for p,h in audio['raw_capture_sha256'].items())
    profile=json.loads((B/'profile_validation.json').read_text());assert profile['bow_anchors_bit_exact']==648
    for name in['expression_raw.mem','expression_normalized.mem']:
        assert(R/'rtl'/name).read_text().split()[:648]==(B/'baseline/rtl'/name).read_text().split()[:648]
    O.mkdir(parents=True,exist_ok=True);firmware=O/'声芯乐动_A6C4_口琴柔化_完整音响版.fs';cp(fs,firmware)
    cp(O/'我和我的祖国_新版口琴_20秒.mp3',O/'口琴试听_A6C4_我和我的祖国20秒.mp3')
    cp(R/'docs/harmonica_refinement_20261102.md',O/'试听与验证说明.md')
    evidence=O/'evidence'
    for pattern in['*.json','*.log','phrase.tsv','zuguo20.tsv','voices32_i2s.txt']:
        for p in B.glob(pattern):
            if not p.name.startswith('pre_'):cp(p,evidence/p.name)
    shutil.copytree(B/'latency',evidence/'latency',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.vvp'))
    for name in[N+'.rpt.txt',N+'.pin.html',N+'_tr_content.html']:cp(B/'impl/pnr'/name,evidence/name)
    source=O/'source';project=source/'fpga';shutil.copytree(B/'src',project/'src',dirs_exist_ok=True)
    prefix=(B/'src').as_posix()+'/'
    for p in(project/'src').rglob('*'):
        if p.suffix in('.v','.vh','.sdc','.cst'):write(p,p.read_text('utf8').replace(prefix,'src/'))
    tree=ET.parse(B/(N+'.gprj'))
    for f in tree.findall('./FileList/File'):f.set('path',f.get('path').replace(prefix,'src/'))
    tree.write(project/(N+'.gprj'),encoding='utf8',xml_declaration=True)
    assert all(not Path(f.get('path')).is_absolute()and(project/f.get('path')).is_file()for f in tree.findall('./FileList/File'))
    for p in(project/'src').rglob('*'):
        if p.suffix in('.v','.vh'):
            for path in re.findall(r'"(src/[^"\n]+)"',p.read_text('utf8')):assert(project/path).is_file(),(p,path)
    write(project/'build.tcl',f'open_project ./{N}.gprj\nset_option -top_module soundcore_speaker_omr_top\nset_option -user_code 0000A6C4\nrun all\n')
    write(project/'build.ps1',"param([string]$GowinShell='D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe')\n$ErrorActionPreference='Stop'\nPush-Location -LiteralPath $PSScriptRoot\ntry { & $GowinShell 'build.tcl'; if ($LASTEXITCODE -ne 0) { throw 'Build failed' } } finally { Pop-Location }\n")
    for p in(R/'scripts').glob('*harmonica*20261102.py'):cp(p,source/'reference_scripts'/p.name)
    for name in['preflight_latency_20261101.py','check_tools_voices_20261102.py','generate_pitch_layout72.py','generate_expression_profile.py']:cp(R/'scripts'/name,source/'reference_scripts'/name)
    cp(R/'tb/tb_harmonica_refinement_capture.v',source/'reference_tb/tb_harmonica_refinement_capture.v')
    cp(R/'config/harmonica_profile_v3_20261102.json',source/'config/harmonica_profile_v3_20261102.json')
    shutil.copytree(B/'baseline',source/'baseline',dirs_exist_ok=True)
    write(source/'重建说明.md','FPGA工程为完整A6C4，打开fpga中的gprj或执行build.ps1可重建；工具Gowin1.9.11.03 Education，目标GW5AT-LV60PG484AC1/I0。所有工程/ROM路径已相对化。reference_scripts/reference_tb保留原工作区目录合同，用于追溯实验，需在原soundcore_2026工作区运行或调整ROOT/输入目录；不是独立安装器。App协议与0.22相同，本包不包含新APK。无硬件烧录动作。\n')
    hashes={p.relative_to(source).as_posix():sha(p)for p in source.rglob('*')if p.is_file()and p.name!='source_hashes.json'}
    write(source/'source_hashes.json',json.dumps(hashes,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(O/'口琴修订_配套源码.zip','w',zipfile.ZIP_DEFLATED,compresslevel=5)as z:
        for p in sorted(source.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(source))
    report=dict(user_code='0x0000A6C4',base='0x0000A623',app_version='0.22-compatible',programming_performed=False,
        pins_unchanged=True,pins=pins,timing=dict(violations,fmax_mhz=fmax,clock_constraint_mhz=12.288),resources=resources,
        audio=audio,voices=voices,latency_simulation=latency,profile=profile,real_speaker_listening_verified=False,
        firmware_sha256=sha(firmware),source_zip_sha256=sha(O/'口琴修订_配套源码.zip'),root_audio_inputs=root_audio)
    write(O/'release.json',json.dumps(report,ensure_ascii=False,indent=2))
    write(R/'build/latest_harmonica_candidate.json',json.dumps(dict(status='ready_for_sram_listening',firmware=str(firmware),
        user_code=report['user_code'],sha256=report['firmware_sha256'],baseline_user_code='0x0000A623',sram_written=False,flash_written=False),ensure_ascii=False,indent=2))
    body=markdown.markdown((O/'试听与验证说明.md').read_text('utf8'),extensions=['tables','fenced_code'])
    metrics=f'<p>实际RTL：强音持续响度差{audio["strong_steady_rms_change_db"]:+.3f}dB；二胡24,000样本逐位一致；32声部仍225/256时钟；16工况数字延迟最大{latency["max_step_to_abs64_i2s_ms"]:.3f}ms（不含功放/喇叭）。完整PNR Setup/Hold违例0/0，Fmax{fmax:.3f}MHz。</p><p>20秒裁剪试听仅在最后10ms淡出，避免中途截断的啪声；原始RTL采样和测量没有淡出处理。</p>'
    clips=''.join(f'<section><h2>{title}</h2><audio controls preload="metadata" src="{file}"></audio><p><a href="{file}">下载MP3</a> · <a href="{file[:-4]}.wav">无损WAV</a></p></section>'for title,file in[
        ('新版口琴 · 6秒短句','口琴_新版短句.mp3'),('同增益对比 · 先旧6秒，后新6秒','口琴_同增益对比_先旧后新.mp3'),
        ('《我和我的祖国》 · 新版20秒','我和我的祖国_新版口琴_20秒.mp3'),('《我和我的祖国》 · A623对照20秒','我和我的祖国_A623口琴_20秒.mp3')])
    write(O/'口琴试听与说明.html',f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>声芯 · 口琴修订试听</title><style>body{{margin:0;background:#0a1720;color:#e2ecef;font:16px/1.85 system-ui,"Microsoft YaHei",sans-serif}}main{{max-width:950px;margin:auto;padding:32px 22px}}section,nav{{padding:20px;margin:18px 0;background:#172e3a;border-radius:16px}}h1{{font-size:30px}}h2{{font-size:21px;color:#51deca}}a{{color:#51deca}}audio{{width:100%}}img{{width:100%;background:white;border-radius:16px}}li{{margin:10px 0}}code{{overflow-wrap:anywhere}}</style><main><h1>口琴音色 · A6C4</h1><p>实际RTL数字试听；相同增益。实物喇叭听感尚待确认，本包没有烧录。</p><nav><a href="{firmware.name}">完整音响固件</a> · <a href="口琴修订_配套源码.zip">配套源码</a> · <a href="release.json">验证清单</a></nav>{metrics}{clips}<img src="口琴频谱与起音.png" alt="实际RTL频谱和起音包络">{body}</main></html>')
    write(O/'SHA256SUMS.txt','\n'.join(f'{sha(p)}  {p.relative_to(O).as_posix()}'for p in sorted(O.rglob('*'))if p.is_file()and p.name!='SHA256SUMS.txt'))
    print(json.dumps({k:report[k]for k in['user_code','timing','resources','firmware_sha256','programming_performed']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
