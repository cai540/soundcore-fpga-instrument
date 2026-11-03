"""Check the current two-song data and real playback/guide/OLED paths."""
import argparse,os,subprocess,sys
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('--prefix',default='product_songs_')
parser.add_argument('--data-modules',nargs='+',default=['tb.test_product_song_data'])
parser.add_argument('--only',nargs='+',help='Resume selected RTL checks after fixing a failed check')
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build'
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'),PYTHONIOENCODING='utf-8')
if not args.only:
    data=subprocess.run([sys.executable,'-m','unittest',*args.data_modules,'-v'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    (BUILD/(args.prefix+'data_test.log')).write_text(data.stdout+data.stderr,encoding='utf-8')
    print(data.stdout+data.stderr,flush=True)
    if data.returncode:sys.exit(data.returncode)
tests={
 'tb_audio_song_full_playback':['song_event_player'],
 'tb_lyric_position':['song_lyric_position'],
 'tb_song_lyric_continuous':['song_autoplay_control','song_event_player','song_lyric_position'],
 'tb_song_lyric_oled_flow':['song_event_player','song_lyric_position','oled_status_ssd1315','oled_i2c_write2','oled_lyric_columns'],
 'tb_score_midi_review_rom':['song_event_player','song_guide_long'],
 'tb_product_song_guide':['song_guide_long'],
 'tb_song_word_articulation':['song_event_player','instrument_texture','synth_voice'],
 'tb_oled_karaoke_render':['oled_lyric_columns'],
 # This last test consumes golden bytes emitted by the previous test.
 'tb_oled_karaoke_integration':['oled_status_ssd1315','oled_i2c_write2','oled_lyric_columns'],
}
if args.only and set(args.only)-set(tests):parser.error('unknown RTL test name')
for name,modules in tests.items():
    if args.only and name not in args.only:continue
    output=BUILD/(args.prefix+name+'.vvp')
    command=[str(TOOL/'iverilog.exe'),'-g2012','-s',name,'-o',str(output),f'tb/{name}.v']+[f'rtl/{m}.v' for m in modules]
    compiled=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
    run=subprocess.run([str(TOOL/'vvp.exe'),str(output)],cwd=ROOT,capture_output=True,text=True)
    text=compiled.stdout+compiled.stderr+run.stdout+run.stderr
    (BUILD/(args.prefix+name+'.log')).write_text(text,encoding='utf-8')
    print(name,run.returncode,text.strip(),flush=True)
    assert not run.returncode and 'PASS:' in text and 'FATAL:' not in text,name
