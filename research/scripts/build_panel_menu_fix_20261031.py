"""Add the missing OLED song menu to the frozen, field-tested 05D8 product."""
from pathlib import Path
import hashlib,json,shutil,subprocess,xml.etree.ElementTree as ET
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/speaker_led8_20261031'
OUT=ROOT/'build/panel_menu_fix_20261031'
SRC=OUT/'baseline'
NAME='soundcore_speaker_omr_60k'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def patch_display(text):
    if 'parameter integer PANEL_MENU' in text:return text
    replacements=[
        ('parameter integer CAPTURE_OVERLAY = 0','parameter integer CAPTURE_OVERLAY = 0,\n    parameter integer PANEL_MENU = 0'),
        ('input wire [1:0] ui_state,','input wire [1:0] ui_state,\n    input wire [7:0] menu_song,'),
        ('reg [1:0] shown_ui_state;','reg [1:0] shown_ui_state;\n    reg [7:0] shown_menu_song;\n    wire menu_active = PANEL_MENU != 0 && shown_ui_state == 2\'d1;\n    wire [7:0] menu_pixels;\n    generate if(PANEL_MENU != 0)begin: menu_layer\n        oled_panel_menu_columns menu(.clk(clk),.song(shown_menu_song[0]),\n            .page(page_index[1:0]),.column(column),.pixels(menu_pixels));\n    end else begin: no_menu_layer\n        assign menu_pixels=0;\n    end endgenerate'),
        ('wire status_changed = capture_live!=shown_capture ||','wire status_changed = (PANEL_MENU != 0 && menu_song != shown_menu_song) ||\n        capture_live!=shown_capture ||'),
        ('shown_ui_state <= 0;','shown_ui_state <= 0;\n            shown_menu_song <= 0;'),
        ('shown_ui_state <= ui_state;','shown_ui_state <= ui_state;\n                    shown_menu_song <= PANEL_MENU != 0 ? menu_song : 8\'d0;'),
        ('tx_payload=capture_active && (page_index<4 || shown_capture[15:8]<10) ? capture_pixels : (page_index>=4) ?',
         'tx_payload=menu_active ? (page_index<4 ? menu_pixels :\n                    force_column(page_index,column,shown_force_buckets)) :\n                    capture_active && (page_index<4 || shown_capture[15:8]<10) ? capture_pixels : (page_index>=4) ?'),
        ('((LYRIC_OVERLAY != 0 && shown_lyric_mode) ? lyric_byte:hanzi_byte);',
         '((LYRIC_OVERLAY != 0 && shown_lyric_mode) ? lyric_byte:hanzi_byte);\n                // A play/pause mark uses only the unused right margin of the meters.\n                if(PANEL_MENU != 0 && !menu_active && !capture_active && page_index==4 &&\n                    column>=116 && column<124 && (shown_ui_state==2 || shown_ui_state==3 ||\n                    shown_playback_state==1 || shown_playback_state==2)) begin\n                    if(shown_ui_state==3 || shown_playback_state==2)\n                        tx_payload=(column<119 || column>=121) ? 8\'h7e : 8\'h00;\n                    else case(column)\n                        116:tx_payload=8\'h7e;117:tx_payload=8\'h3c;118:tx_payload=8\'h3c;\n                        119:tx_payload=8\'h18;120:tx_payload=8\'h18;121:tx_payload=8\'h00;\n                        default:tx_payload=8\'h00;\n                    endcase\n                end')
    ]
    for before,after in replacements:
        assert text.count(before)==1,before
        text=text.replace(before,after)
    return text

def patch_top(text):
    before='.CAPTURE_OVERLAY(UPLOADED_SCORE_ENABLE)'
    after='.CAPTURE_OVERLAY(UPLOADED_SCORE_ENABLE),.PANEL_MENU(1)'
    assert text.count(before)==1
    text=text.replace(before,after)
    before='.vibrato(vibrato_enabled),.ui_state(score_guiding'
    after='.vibrato(vibrato_enabled),.menu_song(song_index),.ui_state(score_guiding'
    assert text.count(before)==1
    return text.replace(before,after)

def run_test(test,sources):
    folder=OUT/'simulation';folder.mkdir(exist_ok=True)
    target=folder/(test+'.vvp')
    compiler='D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe'
    runner='D:/FPGA/_Tools/iverilog-conda/Library/bin/vvp.exe'
    compile_run=subprocess.run([compiler,'-g2012','-s',test,'-o',str(target),
        str(ROOT/'tb'/(test+'.v')),*map(str,sources)],capture_output=True,text=True,cwd=ROOT)
    assert compile_run.returncode==0,(test,compile_run.stdout,compile_run.stderr)
    result=subprocess.run([runner,str(target)],capture_output=True,text=True,cwd=ROOT,timeout=90)
    body=result.stdout+result.stderr
    passed=result.returncode==0 and 'PASS:' in body
    (folder/(test+'.log')).write_text(body,encoding='utf-8')
    print(test+': '+('PASS' if passed else body),flush=True)
    assert passed,test
    return {'test':test,'passed':passed,'output':body}

def main():
    release=json.loads((ROOT/'output/speaker_led8_20261031/release.json').read_text(encoding='utf-8'))
    assert sha(Path(release['firmware']))==release['sha256']
    OUT.mkdir(parents=True,exist_ok=True)
    # Chinese glyphs are rasterized once. A fixed 1 KiB ROM avoids a large glyph mux.
    font=ImageFont.truetype('C:/Windows/Fonts/simhei.ttf',16)
    frames=[]
    for song,title in enumerate(['我和我的祖国','敕勒歌']):
        image=Image.new('1',(128,32));draw=ImageDraw.Draw(image)
        draw.text((0,0),'曲目'+title,font=font,fill=1)
        draw.text((0,16),'K1/K2选曲 K5开始',font=font,fill=1)
        image.resize((768,192)).save(OUT/('menu_'+str(song)+'.png'))
        frames.extend(sum(image.getpixel((x,page*8+y))<<y for y in range(8))
                      for page in range(4) for x in range(128))
    font_path=ROOT/'board/panel_menu_frames.mem'
    font_path.write_text(''.join(f'{x:02x}\n' for x in frames),encoding='ascii')
    proof=[]
    modified=['rtl/oled_status_ssd1315.v','board/pressure_i2s_panel_oled_ble_experiment_top.v']
    for p in (BASE/'baseline').rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(BASE/'baseline').as_posix();target=SRC/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        if p.suffix in ['.v','.vh','.cst','.sdc']:
            original=p.read_text(encoding='utf-8').replace(BASE.as_posix(),OUT.as_posix())
            text=patch_display(original) if rel==modified[0] else patch_top(original) if rel==modified[1] else original
            target.write_text(text,encoding='utf-8')
            if rel not in modified:assert text==original
        else:shutil.copyfile(p,target)
        if rel not in modified:proof.append({'file':rel,'snapshot_sha256':sha(target),'baseline_sha256':sha(p)})
    for rel in ['rtl/oled_panel_menu_columns.v','board/panel_menu_frames.mem']:
        p=ROOT/rel;target=SRC/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if p.suffix=='.v':target.write_text(p.read_text(encoding='utf-8').replace((ROOT/'board').as_posix(),(SRC/'board').as_posix()),encoding='utf-8')
        else:shutil.copyfile(p,target)
    # Update canonical OLED source without copying any older top-level defaults into the release.
    p=ROOT/'rtl/oled_status_ssd1315.v';p.write_text(patch_display(p.read_text(encoding='utf-8')),encoding='utf-8')
    p=ROOT/'board/pressure_i2s_panel_oled_ble_experiment_top.v'
    text=p.read_text(encoding='utf-8')
    if '.PANEL_MENU(1)' not in text:p.write_text(patch_top(text),encoding='utf-8')
    tree=ET.parse(BASE/(NAME+'.gprj'))
    for item in tree.findall('./FileList/File'):
        p=Path(item.attrib['path'])
        if p.is_relative_to(BASE/'baseline'):item.set('path',(SRC/p.relative_to(BASE/'baseline')).as_posix())
        elif p.is_file():proof.append({'external_input':str(p),'sha256':sha(p)})
    ET.SubElement(tree.find('./FileList'),'File',path=(SRC/'rtl/oled_panel_menu_columns.v').as_posix(),type='file.verilog',enable='1')
    project=OUT/(NAME+'.gprj');tree.write(project,encoding='utf-8',xml_declaration=True)
    assert '.OMR_ENABLE(1)' in (SRC/modified[1]).read_text(encoding='utf-8')
    (OUT/'verification_reuse.json').write_text(json.dumps({'changed_files':modified,'added_files':['rtl/oled_panel_menu_columns.v','board/panel_menu_frames.mem'],'files':proof,
        'scope':'Audio, pressure, five-key controller, songs, BLE, model and pin constraints unchanged; OLED menu snapshot/rendering and its top-level song input only.'},ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copyfile(BASE/'tests.json',OUT/'tests.json')
    sources=[SRC/'rtl'/name for name in ['oled_i2c_write2.v','oled_status_ssd1315.v','oled_panel_menu_columns.v','oled_lyric_columns.v','oled_capture_columns.v','front_panel_five_keys.v']]
    tests=[]
    for test in ['tb_oled_i2c_write2','tb_oled_reconnect','tb_oled_dual_address','tb_oled_event_refresh',
                 'tb_oled_force_geometry','tb_oled_karaoke_integration','tb_capture_oled_i2c',
                 'tb_front_panel_auto_ble','tb_panel_oled_menu_flow']:
        tests.append(run_test(test,sources))
        (OUT/'panel_menu_tests.json').write_text(json.dumps(tests,ensure_ascii=False,indent=2),encoding='utf-8')
    meta=json.loads((BASE/'build_metadata.json').read_text(encoding='utf-8'))
    meta.update(panel_menu_fix=True,baseline_firmware_sha256=release['sha256'],baseline_user_code=release['user_code'],
        modified_copied_files=modified+['rtl/oled_panel_menu_columns.v','board/panel_menu_frames.mem'],rtl_unchanged_verified=False,
        tests_reused_from=str(BASE/'tests.json'),sram_written=False,flash_written=False)
    (OUT/'build_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    tcl=OUT/'build.tcl';tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun all\n',encoding='utf-8')
    print('Building complete product with OLED song menu; Flash unchanged',flush=True)
    with (OUT/'build.log').open('w',encoding='utf-8') as log:
        result=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0,'inspect build.log'
    print('Complete Gowin build PASS',flush=True)

if __name__=='__main__':main()
