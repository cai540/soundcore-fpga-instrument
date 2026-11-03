"""Stage code, portable frozen FPGA project, evidence and public demo variant."""
from pathlib import Path
import hashlib,json,os,re,shutil,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'build/submission_20261103';OUT=ROOT/'output/submission_20261103'
FULL=B/'full_source/声芯乐动';PUB=B/'github_source'
FROZEN=ROOT/'build/contest_audit_20261103/firmware'
IGNORE={'build','output','.gradle','.kotlin','node_modules','__pycache__','.git','.pytest_cache','.venv_audio','.audio_models','.score-api','tmp','venv'}
EXT={'.py','.v','.vh','.sv','.tcl','.sdc','.cst','.ys','.bat','.ps1','.kt','.kts','.toml','.json','.mem','.hex','.mi','.html','.css','.js','.mjs','.ts','.md','.txt','.xml','.svg','.gprj','.yaml','.yml','.properties','.coe','.sh'}
TEXT=EXT-{'.onnx','.wasm','.gz','.png','.jpg','.jar'}
SECRET=re.compile(r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{25,}|AKIA[A-Z0-9]{16})\b')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,t):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8')
def cp(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)

def copy_tree(src,dst,all_assets=False):
    for d,dirs,files in os.walk(src):
        dirs[:]=[x for x in dirs if x not in IGNORE and not x.startswith('.')]
        for name in files:
            p=Path(d)/name;rel=p.relative_to(src)
            if name in {'local.properties','config.json','score_api_bailian.json'} or name.startswith('.env'):continue
            if not all_assets and p.suffix.lower() not in EXT:continue
            if p.suffix in {'.wav','.mp3','.mp4','.m4a','.mid','.midi','.fs','.zip','.rar','.pdf','.docx','.exe','.dll','.log','.vcd','.png','.jpg','.jpeg'} and not all_assets:continue
            cp(p,dst/rel)

def stage():
    assert not FULL.exists() and not PUB.exists(),'Refuse to overwrite an existing staging directory'
    FULL.mkdir(parents=True);PUB.mkdir(parents=True)
    # Canonical build entry: exact B713 snapshot, not the mutable board folder.
    copy_tree(FROZEN/'src',FULL/'fpga/src',True)
    cp(FROZEN/'soundcore_speaker_omr_60k.gprj',FULL/'fpga/soundcore.gprj')
    old=FROZEN.as_posix()
    mutations=[]
    for p in (FULL/'fpga').rglob('*'):
        if not p.is_file() or p.suffix not in EXT:continue
        t=p.read_text(encoding='utf-8');s=t.replace(old,'@FPGA_ROOT@')
        if p.suffix=='.gprj':s=s.replace('@FPGA_ROOT@/','')
        if s!=t:put(p,s);mutations.append(str(p.relative_to(FULL)))
    put(FULL/'fpga/configure.py',CONFIGURE)
    put(FULL/'fpga/build.tcl','open_project ./soundcore.gprj\nset_option -top_module soundcore_speaker_omr_top\nset_option -user_code 0000B713\nset_option -place_option 4\nset_option -route_option 0\nrun all\n')
    cp(FROZEN/'frozen_inputs.json',FULL/'evidence/B713_original_frozen_hashes.json')
    put(FULL/'evidence/path_relocation.json',json.dumps({'changed_only_for_portability':mutations,'canonical_root':'B713 frozen source; original hashes retained separately','bit_identical_rebuild':'not asserted; rerun vendor build after relocation'},ensure_ascii=False,indent=2))
    # Preserve all authored source, including historical experiments, without generated binaries.
    for name in ['rtl','board','scripts','tools','soundcore_audio','fpga_omr','score_api','web','tests','tb','evaluation','examples','songs','config']:
        copy_tree(ROOT/name,FULL/'research'/name)
    for name in ['pyproject.toml','run_sim.bat','verify_additive32_balance.py','verify_additive32_spectrum.py','verify_spectrum.py','verify_spectrum32.py','import_guide_song.py']:
        if (ROOT/name).exists():cp(ROOT/name,FULL/'research'/name)
    copy_tree(ROOT/'app/android',FULL/'android',True)
    # Tests' snapshots are build inputs; source MP3s and user photographs are deliberately absent.
    docs=['wiring_manual_data_2026-10-31.json','acceptance_lab_20261102.md','contest_rule_gate_2026-09-24.md','innovation_roadmap_2026-10-28.md','harmonica_refinement_20261102.md']
    for name in docs:
        if (ROOT/'docs'/name).exists():cp(ROOT/'docs'/name,FULL/'docs'/name)
    ev=ROOT/'output/contest_lab_20261103'
    for name in ['赛题逐项对照.json','赛题逐项对照.csv','release_manifest.json']:
        cp(ev/name,FULL/'evidence'/name)
    # Retain quantitative evidence, not temporary programming executables or private machine logs.
    copy_tree(ev/'验证记录',FULL/'evidence/validation')
    for p in (FROZEN/'impl/pnr').glob('*'):
        if p.suffix in {'.html','.txt','.rpt'}:cp(p,FULL/'evidence/pnr'/p.name)
    cp(ROOT/'output/product_repair_20261103/验证记录/expression_optimization.json',FULL/'evidence/expression_optimization.json')
    rec=json.loads((FROZEN/'programming_latest_sram.json').read_text(encoding='utf-8-sig'))
    rec={k:rec[k] for k in ['time','sha256','device','device_id','expected_user_code','flash_written','sram_program_finished','user_code_readback_matched','physical_audio_verified','preflight']}
    put(FULL/'evidence/sram_programming.json',json.dumps(rec,ensure_ascii=False,indent=2))
    cp(ROOT/'build/contest_audit_20261103/source/official_topic2.txt',FULL/'docs/official_topic2.txt')
    cp(__file__,FULL/'submission_tools'/Path(__file__).name)
    put(FULL/'README.md',README)
    put(FULL/'THIRD_PARTY_NOTICES.md',NOTICES)
    put(FULL/'LICENSE',LICENSE)
    put(FULL/'.gitignore',GITIGNORE)
    put(FULL/'android/BUILD.md','JDK 17; Gradle 8.13; Android SDK compileSdk 36, targetSdk 35, minSdk 26.\nRun gradle :app:assembleDebug and gradle :app:testDebugUnitTest. Create local.properties with your sdk.dir; no API key is required.\nSnapshot tests: gradle :app:verifyPaparazziDebug. Instrumented/device tests need an actual phone and permissions. Do not distribute the local debug keystore as project source.\n')
    # Public source shares authored core and the active Android app, with no private song recordings.
    for name in ['fpga','android','docs','evidence']:
        copy_tree(FULL/name,PUB/name,True)
    for name in ['soundcore_audio','fpga_omr','tb','tests','evaluation','tools','scripts','config']:
        copy_tree(FULL/'research'/name,PUB/'research'/name)
    cp(FULL/'research/pyproject.toml',PUB/'research/pyproject.toml')
    for name in ['README.md','THIRD_PARTY_NOTICES.md','LICENSE','.gitignore']:cp(FULL/name,PUB/name)
    put(PUB/'PUBLIC_DEMO.md',PUBLIC_DEMO)
    generate_public_demo(PUB)
    # Strip concrete machine account paths and known token shapes from all staged text.
    audit=[]
    for base in [FULL,PUB]:
        for p in base.rglob('*'):
            if not p.is_file() or p.suffix.lower() not in TEXT:continue
            try:t=p.read_text(encoding='utf-8-sig')
            except UnicodeError:continue
            found=SECRET.findall(t)
            if found:audit.append({'stage':base.name,'path':p.relative_to(base).as_posix(),'redactions':len(found)})
            t=SECRET.sub('REDACTED_CREDENTIAL',t)
            # Windows user profiles are neither a dependency nor anonymous contest content.
            t=t.replace('C:/Users/YOUR_USER','C:/Users/YOUR_USER').replace('C:\\Users\\YOUR_USER','C:\\Users\\YOUR_USER').replace('C:\\\\Users\\\\Lwc01','C:\\\\Users\\\\YOUR_USER')
            put(p,t)
    for base in [FULL,PUB]:
        manifest={p.relative_to(base).as_posix():digest(p) for p in sorted(base.rglob('*')) if p.is_file()}
        put(base/'SOURCE_SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    summary={str(x.relative_to(B)):{'files':sum(p.is_file() for p in x.rglob('*')),'bytes':sum(p.stat().st_size for p in x.rglob('*') if p.is_file())} for x in [FULL,PUB]}
    put(B/'source_staging_audit.json',json.dumps({'sizes':summary,'credential_redactions':audit,'raw_user_audio_included':False,'api_key_files_included':False},ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False))

def generate_public_demo(base):
    assets=base/'fpga/src/assets';changes=[]
    # The publication is an explicitly different demo-data variant, not bit-identical B713.
    for p in assets.glob('*'):
        if re.search(r'_(?:lyric_(?:words|starts|guide)_\d|lyric_text|lyric_phrases)\.mem$',p.name):
            lines=p.read_text().splitlines();put(p,'\n'.join('0'*len(x.strip()) for x in lines)+'\n');changes.append(p.name)
    seq=[0,0,4,4,5,5,4,3,3,2,2,1,1,0]
    for idx in [0,1]:
        p=next(assets.glob(f'*_song_{idx}.mem'))
        words=[((700 if i%7==6 else 350)<<6)|(3<<3)|n for i,n in enumerate(seq)]
        put(p,'\n'.join(f'{x:06X}' for x in words)+'\n');changes.append(p.name)
    catalog=next(assets.glob('*_product_song_catalog.vh'))
    t=catalog.read_text()
    for idx in [0,1]:
        for field,value in [('EVENTS',len(seq)),('WORDS',1),('DURATION_MS',sum(700 if i%7==6 else 350 for i in range(len(seq))))]:
            t=re.sub(rf'(`define PRODUCT_SONG{idx}_{field}) \d+',rf'\g<1> {value}',t)
    put(catalog,t);changes.append(catalog.name)
    # UI names reflect the public-domain demonstration data.
    for p in (base/'android/app/src').rglob('*'):
        if p.is_file() and p.suffix in {'.kt','.json','.js','.html'}:
            try:t=p.read_text(encoding='utf-8')
            except UnicodeError:continue
            put(p,t.replace('我和我的祖国','公版示例甲').replace('敕勒歌','公版示例乙'))
    for p in (base/'fpga/src').rglob('*.v'):
        t=p.read_text(encoding='utf-8');put(p,t.replace('我和我的祖国','公版示例甲').replace('敕勒歌','公版示例乙'))
    put(base/'evidence/public_demo_asset_changes.json',json.dumps({'variant':'public-domain demo; not B713-identical','changed_assets':changes,'melody':'Twinkle Twinkle Little Star, public-domain traditional melody','lyric_timing':'cleared; no copyrighted lyric content published'},ensure_ascii=False,indent=2))

CONFIGURE='''from pathlib import Path
import xml.etree.ElementTree as E
r=Path(__file__).resolve().parent
for p in (r/'src').rglob('*'):
 if p.is_file() and p.suffix in {'.v','.vh','.tcl','.sdc'}:
  t=p.read_text(encoding='utf-8');s=t.replace('@FPGA_ROOT@',r.as_posix())
  if s!=t:p.write_text(s,encoding='utf-8')
p=r/'soundcore.gprj';tree=E.parse(p)
for f in tree.findall('.//File'):
 v=f.get('path');q=Path(v)
 if not q.is_absolute():q=r/q
 assert q.is_file(),q
 f.set('path',q.as_posix())
tree.write(p,encoding='utf-8',xml_declaration=True)
print('Configured',r)
'''
README='''# 声芯乐动 / Soundcore FPGA Instrument

纯HDL多维交互乐器：32个独立声部、七路压力输入、滑杆、EC11、五键、OLED、LED、I²S扬声器与Android原生App。

## 版本和证据边界
本提交基础为B713（GW5AT-60B，MAX98357A）与Android 0.24-scope-lab。布局布线、RTL和软件测试证据位于evidence。B713存在SRAM成功下载读回记录，未据此宣称真实音频或5ms延迟已验收。Flash仍需根据板上实际记录确认。

## 从源码开始
1. 解压路径建议仅含英文。`fpga`是当前唯一正式构建入口；`research/board`等包含历史实验，不应直接用于烧录。
2. 在`fpga`执行`python configure.py`，使冻结的文件/ROM引用指向本机路径。用支持GW5AT-60B的Gowin IDE打开soundcore.gprj，顶层soundcore_speaker_omr_top；或在此目录运行`gw_sh build.tcl`。保留CST；不要在未核对实板时改针或上电。
3. Android需要JDK17、Gradle8.13和Android SDK36（minSdk26）。在android运行`gradle :app:assembleDebug`；测试`gradle :app:testDebugUnitTest`。sdk.dir写入本机local.properties，不提交SDK或凭据。首次构建需要下载开源依赖，安装后的内置识别不需云API。
4. Python研究算法：进入research，`python -m pip install -e .`。运行原生测试还需pytest、Pillow。部分历史脚本使用原开发目录，不是便携构建入口。用户提供的原始音频、照片和私人样本不随代码分发。

## 结构
- fpga/src：B713冻结HDL、约束、IP包装及必要表/模型/曲谱ROM。
- android：完整活动App源码、内置ONNX/OCR模型、30首公版书架数据、单元测试及界面快照。
- research：算法、训练/导出、仿真测试台及历史实验源码。完整竞赛RAR比公开仓库保留更多历史源和内置曲目数据。
- docs：接线数据、赛题原文快照、实现说明。
- evidence：原始冻结哈希、路径迁移说明、PNR、回归摘要与SRAM读回记录。

## 音乐资产和公开版本
完整竞赛RAR保留当前内置曲目事件和歌词数据以供项目复现；不代表授予任何原作品权利。公开GitHub使用公版示例数据，详见PUBLIC_DEMO.md；公开版不与B713曲目ROM位级一致。项目音频实时合成，不将歌曲PCM音频存储回放冒充合成。

## 原创与第三方
共享帧级表情流水线、压力事件策略、识别后事件解码与七键映射、通信及产品集成为项目实现。CREPE Tiny基础权重、Tesseract、ONNX运行时及Gowin厂商IP不冒称原创。许可和归属见THIRD_PARTY_NOTICES.md。MIT仅覆盖有权许可的项目原创代码，不改变第三方条款。

## 更新
修改源码后提交新commit并重新生成报告/证据，记录固件UserCode与App版本。实验室数据只能填写实测，不以仿真或图形渲染替代。
'''
PUBLIC_DEMO='''# 公开仓库与竞赛完整工程的差别

公开仓库包含当前合成架构、活动App、识别基础模型和通用算法，但不公开私人录音/照片。两首竞赛曲目的音符及歌词ROM已替换为《小星星》公版旋律示例和空歌词时间表；App中的曲名同步改为示例名。OLED固有菜单字模保留，不构成歌曲音频。图像模型/识别代码未作歌曲特例替换。

公开示例的音频算法基于B713，曲目数据及显示菜单内容不同，因此没有用B713的PNR/时序/音准证据宣称公开示例已上板；重新构建和测试后应使用新的版本标识。竞赛完整RAR保留当前两首内置曲目的原数据和冻结哈希，公开仓库与RAR并非文件逐字节相同。

请先运行fpga/configure.py，再构建。不要用公开示例固件覆盖已验收的竞赛Flash而没有比较结果。
'''
NOTICES='''# 第三方与资产归属

1. CREPE / torchcrepe基础预训练权重，MIT。当前crepe_tiny.json明确说明无项目重训练。ONNX导出不改变基础权重的来源。保留android/app/src/main/assets/open_source_licenses中的CREPE与TORCHCREPE许可证。
2. ONNX Runtime，MIT；保留ONNX_RUNTIME_LICENSE.txt。Gradle依赖按其原许可证使用。
3. Tesseract.js / OCR训练数据、WASM依赖：保留android/app/src/main/assets/offline/ocr中的LICENSE及TRAINEDDATA_LICENSE、打包JS内许可证注释；相应上游许可证优先。
4. librosa相关设计/工具归属见随包ISC声明；其他Python依赖适用各自许可。
5. Gowin PLL、BRAM仿真原语与厂商生成IP按高云原有条款使用；仅分发项目已有包装源与配置，不分发IDE、下载器或厂商加密工具。请从厂商安装相应工具与仿真库。
6. 公版书架旋律使用传统/公版乐曲及已有来源说明，各JSON中source字段保留；编配不是原录音。完整竞赛工程中两首现代歌曲事件/歌词数据来源于提交者提供材料，不纳入项目MIT许可。公开仓库使用单独公版示例。
7. 现场照片、录音、人声分离文件、API凭据、SDK/编译缓存、电脑用户名与调试签名私钥不属于公开源码分发内容。
8. 本项目原创贡献集中于HDL调度与资源复用、压力事件策略、识别证据融合/事件转换和系统联动。不宣称通用DDS、ADSR、FFT或第三方模型由项目首创。
'''
LICENSE='''MIT License

Copyright (c) 2026 Soundcore Project contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of the original project software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY.

This license covers original project code only. Third-party model weights, OCR data, vendor IP, and musical compositions/lyrics retain their separate terms; see THIRD_PARTY_NOTICES.md. No license to third-party music is granted.
'''
GITIGNORE='''**/build/
**/.gradle/
**/.kotlin/
**/__pycache__/
**/.pytest_cache/
**/local.properties
.env*
*.jks
*.keystore
*.fs
*.apk
*.wav
*.mp3
*.vcd
'''

if __name__=='__main__':stage()
