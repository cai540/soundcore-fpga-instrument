"""Freeze 0926 and integrate native guide/demo selection with the existing player."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/panel_menu_fix_20261031'
OUT=ROOT/'build/native_panel_playback_20261031'
SRC=OUT/'baseline';NAME='soundcore_speaker_omr_60k'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def replace_once(text,before,after):
    assert text.count(before)==1,before
    return text.replace(before,after)

def display_patch(text):
    if 'parameter integer PRODUCT_PANEL' in text:return text
    text=replace_once(text,'parameter integer PANEL_MENU = 0','parameter integer PANEL_MENU = 0,\n    parameter integer PRODUCT_PANEL = 0')
    text=replace_once(text,'input wire [7:0] menu_song,','input wire [7:0] menu_song,\n    input wire menu_mode_select,menu_mode_cursor,demo_mode,')
    text=replace_once(text,'reg [7:0] shown_menu_song;','reg [7:0] shown_menu_song;\n    reg shown_mode_select,shown_mode_cursor,shown_demo_mode;')
    before='''        oled_panel_menu_columns menu(.clk(clk),.song(shown_menu_song[0]),
            .page(page_index[1:0]),.column(column),.pixels(menu_pixels));'''
    after='''        if(PRODUCT_PANEL != 0)begin: product_menu
            oled_panel_product_menu_columns menu(.clk(clk),.song(shown_menu_song[0]),
                .demo_mode(shown_demo_mode),.mode_menu(shown_mode_select),.mode_cursor(shown_mode_cursor),
                .page(page_index[1:0]),.column(column),.pixels(menu_pixels));
        end else begin: legacy_menu
            oled_panel_menu_columns menu(.clk(clk),.song(shown_menu_song[0]),
                .page(page_index[1:0]),.column(column),.pixels(menu_pixels));
        end'''
    text=replace_once(text,before,after)
    text=replace_once(text,'wire status_changed = (PANEL_MENU != 0 && menu_song != shown_menu_song) ||',
        'wire status_changed = (PRODUCT_PANEL != 0 && (menu_mode_select!=shown_mode_select ||\n        menu_mode_cursor!=shown_mode_cursor || demo_mode!=shown_demo_mode)) ||\n        (PANEL_MENU != 0 && menu_song != shown_menu_song) ||')
    text=replace_once(text,'shown_menu_song <= 0;','shown_menu_song <= 0;\n            shown_mode_select<=0;shown_mode_cursor<=0;shown_demo_mode<=0;')
    text=replace_once(text,"shown_menu_song <= PANEL_MENU != 0 ? menu_song : 8'd0;",
        "shown_menu_song <= PANEL_MENU != 0 ? menu_song : 8'd0;\n                    shown_mode_select<=PRODUCT_PANEL != 0 && menu_mode_select;\n                    shown_mode_cursor<=PRODUCT_PANEL != 0 && menu_mode_cursor;\n                    shown_demo_mode<=PRODUCT_PANEL != 0 && demo_mode;")
    text=replace_once(text,"if(shown_ui_state==3 || shown_playback_state==2)",
        "if(PRODUCT_PANEL != 0 && shown_playback_state==3)\n                        tx_payload=8'h3c;\n                    else if(shown_ui_state==3 || shown_playback_state==2)")
    return text

def player_patch(text):
    if '8\'d4: begin active<=1;paused<=1;restart_pulse<=1;end' in text:return text
    return replace_once(text,"8'd3: if (active) paused<=0;",
        "8'd3: if (active) paused<=0;\n                    8'd4: begin active<=1;paused<=1;restart_pulse<=1;end // local rewind/pause")

def guide_patch(text):
    if 'input wire restart,' in text:return text
    text=replace_once(text,'input wire rst_n,','input wire rst_n,\n    input wire restart,')
    return replace_once(text,"if (ui_state == 2'd2 && previous_state != 2'd2 &&",
        "if (restart) begin\n                step_index <= 0;completed <= 0;previous_state <= 2'd3;\n            end else if (ui_state == 2'd2 && previous_state != 2'd2 &&")

def top_patch(text):
    text=replace_once(text,'wire [7:0] song_index;',
        'wire [7:0] song_index,menu_song_index;\n    wire demo_mode,mode_menu,mode_cursor,local_player_valid,guide_restart;\n    wire [7:0] local_player_value,player_command_value;\n    wire player_command_valid;')
    before='''    song_autoplay_control autoplay_control (
        .clk(clk_audio),.rst_n(run_n),.command_valid(remote_valid || score_start),
        .command_type(score_start ? 8'h23 : remote_type),.command_value(score_start ? 8'd0 : remote_value),'''
    after='''    song_transport_router transport_router(
        .local_valid(local_player_valid),.local_value(local_player_value),
        .remote_valid(remote_valid),.remote_type(remote_type),.remote_value(remote_value),
        .score_start(score_start),.command_valid(player_command_valid),.command_value(player_command_value));
    song_autoplay_control autoplay_control (
        .clk(clk_audio),.rst_n(run_n),.command_valid(player_command_valid),
        .command_type(8'h23),.command_value(player_command_value),'''
    text=replace_once(text,before,after)
    start=text.index('    front_panel_guide_bridge #(')
    end=text.index('    song_guide_long #(',start)
    text=text[:start]+'''    front_panel_product panel_guide (
        .clk(clk_audio),.rst_n(run_n),
        .bank_down_n(panel_bank_down_n),.bank_up_n(panel_bank_up_n),
        .timbre_n(panel_timbre_n),.song_back_n(panel_song_back_n),.play_pause_n(panel_play_pause_n),
        .enc_s1_n(enc_s1_n),.enc_s2_n(enc_s2_n),.enc_key_n(enc_key_n),
        .remote_valid(remote_valid || score_start),.remote_type(score_start ? 8'h15 : remote_type),
        .remote_value(score_start ? 8'd0 : remote_value),.remote_payload(remote_payload),
        .player_finished(autoplay_finished),.bank(ui_bank),.timbre_select(timbre_select),
        .ui_state(ui_state),.song_index(song_index),.menu_song_index(menu_song_index),
        .song_selected(song_selected),.demo_mode(demo_mode),.mode_menu(mode_menu),.mode_cursor(mode_cursor),
        .volume_level(volume_level),.vibrato_enabled(vibrato_enabled),.vibrato_depth(vibrato_depth),
        .depth_edit(depth_edit),.auth_pending(auth_pending),.remote_write_allowed(panel_write_allowed),
        .guide_button_led(guide_button_led_o),.player_command_valid(local_player_valid),
        .player_command(local_player_value),.guide_restart(guide_restart)
    );
'''+text[end:]
    text=replace_once(text,'.clk(clk_audio),.rst_n(run_n),.ui_state(ui_state),',
        ".clk(clk_audio),.rst_n(run_n),.restart(guide_restart),.ui_state(demo_mode ? 2'd0 : ui_state),")
    text=replace_once(text,"ui_state == 2'd2 && !guide_complete ?","!demo_mode && ui_state == 2'd2 && !guide_complete ?")
    text=replace_once(text,'.PANEL_MENU(1)) display (','.PANEL_MENU(1),.PRODUCT_PANEL(1)) display (')
    text=replace_once(text,'.menu_song(song_index),',
        '.menu_song(menu_song_index),.menu_mode_select(mode_menu),.menu_mode_cursor(mode_cursor),.demo_mode(demo_mode),')
    text=replace_once(text,'.song_index(song_index),.guide_step(displayed_song_step),',
        '.song_index(menu_song_index),.guide_step(displayed_song_step),')
    return text

def main():
    release=json.loads((ROOT/'output/panel_menu_fix_20261031/release.json').read_text(encoding='utf-8'))
    assert sha(Path(release['firmware']))==release['sha256']
    OUT.mkdir(parents=True,exist_ok=True)
    # Mode is visible in the song title. Two separate mode-selection frames show the cursor.
    font=ImageFont.truetype('C:/Windows/Fonts/simhei.ttf',16);frames=[]
    for frame in range(8):
        im=Image.new('1',(128,32));draw=ImageDraw.Draw(im)
        if frame<4:
            draw.text((0,0),('示范' if frame>=2 else '指引')+['我和我的祖国','敕勒歌'][frame%2],font=font,fill=1)
            draw.text((0,16),'K1/K2选曲 K5开始',font=font,fill=1)
        elif frame<6:
            draw.text((0,0),'演奏模式 '+('听示范' if frame==5 else '我来弹'),font=font,fill=1)
            draw.text((0,16),'K1/K2选择 K5确认',font=font,fill=1)
        frames.extend(sum(im.getpixel((x,page*8+y))<<y for y in range(8)) for page in range(4) for x in range(128))
        im.resize((768,192)).save(OUT/f'menu_{frame}.png')
    (ROOT/'board/panel_product_menu_frames.mem').write_text(''.join(f'{v:02x}\n' for v in frames),encoding='ascii')
    # Three real timed notes in each tiny regression ROM; production song assets are never replaced.
    for song in range(2):
        words=[(500<<6)|((i+song)<<3)|((i*2+song)%7) for i in range(3)]
        (OUT/f'native_song{song}.mem').write_text(''.join(f'{v:06x}\n' for v in words),encoding='ascii')
    transforms={'rtl/oled_status_ssd1315.v':display_patch,'rtl/song_autoplay_control.v':player_patch,
        'rtl/song_guide_long.v':guide_patch,'board/pressure_i2s_panel_oled_ble_experiment_top.v':top_patch}
    proof=[]
    for p in (BASE/'baseline').rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(BASE/'baseline').as_posix();target=SRC/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if p.suffix in ['.v','.vh','.cst','.sdc']:
            original=p.read_text(encoding='utf-8').replace(BASE.as_posix(),OUT.as_posix())
            text=transforms[rel](original) if rel in transforms else original
            target.write_text(text,encoding='utf-8')
            if rel not in transforms:assert text==original
        else:shutil.copyfile(p,target)
        if rel not in transforms:proof.append({'file':rel,'snapshot_sha256':sha(target),'baseline_sha256':sha(p)})
    added=['rtl/front_panel_product.v','rtl/song_transport_router.v','rtl/oled_panel_product_menu_columns.v','board/panel_product_menu_frames.mem']
    for rel in added:
        p=ROOT/rel;target=SRC/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if p.suffix=='.v':target.write_text(p.read_text(encoding='utf-8').replace((ROOT/'board').as_posix(),(SRC/'board').as_posix()),encoding='utf-8')
        else:shutil.copyfile(p,target)
    for rel,transform in transforms.items():
        if rel.startswith('board/'):continue # Preserve unrelated canonical top-level differences.
        p=ROOT/rel;p.write_text(transform(p.read_text(encoding='utf-8')),encoding='utf-8')
    tree=ET.parse(BASE/(NAME+'.gprj'))
    for item in tree.findall('./FileList/File'):
        p=Path(item.attrib['path'])
        if p.is_relative_to(BASE/'baseline'):item.set('path',(SRC/p.relative_to(BASE/'baseline')).as_posix())
        elif p.is_file():proof.append({'external_input':str(p),'sha256':sha(p)})
    for rel in added:
        if rel.endswith('.v'):ET.SubElement(tree.find('./FileList'),'File',path=(SRC/rel).as_posix(),type='file.verilog',enable='1')
    project=OUT/(NAME+'.gprj');tree.write(project,encoding='utf-8',xml_declaration=True)
    (OUT/'verification_reuse.json').write_text(json.dumps({'changed_files':list(transforms),'added_files':added,'files':proof,
        'scope':'Audio synthesis/effects, pressure curve/calibration, all GPIO constraints, production songs, BLE decoder and OMR frozen; native panel/menu and song transport only.'},ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copyfile(BASE/'tests.json',OUT/'tests.json')
    sources=[SRC/'rtl'/n for n in ['oled_i2c_write2.v','oled_status_ssd1315.v','oled_panel_menu_columns.v','oled_panel_product_menu_columns.v','oled_lyric_columns.v','oled_capture_columns.v','front_panel_five_keys.v','front_panel_product.v','song_transport_router.v','song_autoplay_control.v','song_event_player.v','song_guide_long.v']]
    results=[];sim=OUT/'simulation';sim.mkdir(exist_ok=True)
    for test in ['tb_oled_i2c_write2','tb_oled_reconnect','tb_oled_dual_address','tb_oled_event_refresh',
        'tb_oled_force_geometry','tb_oled_karaoke_integration','tb_capture_oled_i2c','tb_panel_oled_menu_flow',
        'tb_native_panel_transport','tb_native_panel_oled_flow']:
        binary=sim/(test+'.vvp')
        c=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe','-g2012','-s',test,'-o',str(binary),str(ROOT/'tb'/(test+'.v')),*map(str,sources)],capture_output=True,text=True,cwd=ROOT)
        assert c.returncode==0,(test,c.stdout,c.stderr)
        r=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/vvp.exe',str(binary)],capture_output=True,text=True,cwd=ROOT,timeout=90)
        body=r.stdout+r.stderr;passed=r.returncode==0 and 'PASS:'in body
        (sim/(test+'.log')).write_text(body,encoding='utf-8')
        results.append({'test':test,'passed':passed,'output':body})
        (OUT/'panel_menu_tests.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(test+': '+('PASS'if passed else body),flush=True);assert passed,test
    subprocess.run([sys.executable,str(ROOT/'scripts/check_native_demo_audio_20261031.py')],check=True,cwd=ROOT)
    meta=json.loads((BASE/'build_metadata.json').read_text(encoding='utf-8'))
    meta.update(panel_menu_fix=True,panel_native_transport=True,baseline_firmware_sha256=release['sha256'],baseline_user_code=release['user_code'],
        modified_copied_files=list(transforms)+added,rtl_unchanged_verified=False,tests_reused_from=str(BASE/'tests.json'),sram_written=False,flash_written=False)
    (OUT/'build_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    tcl=OUT/'build.tcl';tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun all\n',encoding='utf-8')
    print('Building complete native guide/demo product',flush=True)
    with (OUT/'build.log').open('w',encoding='utf-8')as log:r=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
    assert r.returncode==0,'inspect build.log'
    print('Complete Gowin build PASS',flush=True)

if __name__=='__main__':main()
