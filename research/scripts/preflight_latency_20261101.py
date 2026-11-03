"""Read-only latency preflight of the frozen 7B69 speaker product. No hardware writes."""
from pathlib import Path
import os,re,json,subprocess,hashlib,argparse,xml.etree.ElementTree as ET
from simulation_sources import iverilog_sources
parser=argparse.ArgumentParser();parser.add_argument('--fallback',action='store_true')
parser.add_argument('--source-build',default='build/natural_seven_20261101')
parser.add_argument('--out');parser.add_argument('--all-octaves',action='store_true')
parser.add_argument('--pressed',type=int,default=2200);parser.add_argument('--baseline',type=int,default=1000)
parser.add_argument('--threshold',type=int,default=64)
args=parser.parse_args();assert 0<=args.baseline<args.pressed<=4095
R=Path(__file__).resolve().parents[1];F=R/args.source_build
O=R/(args.out or ('build/latency_preflight_20261101/fallback'if args.fallback else 'build/latency_preflight_20261101'));O.mkdir(parents=True,exist_ok=True)
os.environ['TEMP']=os.environ['TMP']=str(R/'tmp')
source=(R/'tb/tb_physical_latency.v').read_text(encoding='utf8')
source=source.replace('integer kind,pad,cycles,fd,slot=0;','integer kind,pad,bank_case,cycles,fd,slot=0;\n    reg[2:0] bank=2;')
source=source.replace('reg clk=0,rst_n=0,timbre=1,measuring=0,seen=0;','reg clk=0,rst_n=0,timbre=1,measuring=0,seen=0,first_seen=0,strike_seen=0;')
source=source.replace('real began,latency;','real began,latency,first_time,strike_time;')
source=source.replace('.REMOTE_ENABLE(1),.EFFECTS_AVAILABLE(1),.OFFLINE_PLAYER(1)',
    '.REMOTE_ENABLE(1),.EFFECTS_AVAILABLE(1),.OFFLINE_PLAYER(1),.EARLY_FORCE_ENABLE(1),.CONTINUOUS_EXPRESSION(1)')
source=source.replace(".panel_bank(3'd0)",".panel_key(4'd0),.guide_override(1'b0),.guide_pad(3'd0),.guide_note(7'd0),.remote_absolute(1'b0),.remote_note(7'd0),.panel_bank(bank)")
source=source.replace(".autoplay_note_index(6'd0)",".autoplay_note_index(7'd0)")
source=source.replace('    always @(posedge bclk)if(rst_n)begin','''    always @(posedge clk)if(measuring && !strike_seen && dut.strike_valid)begin
        strike_seen=1;strike_time=$realtime-began;
    end
    always @(posedge bclk)if(rst_n)begin''')
source=source.replace('        if(!lr && slot==16 && measuring && !seen &&','''        if(!lr && slot==16 && measuring && !first_seen && $signed(word_value)!=0)begin
            first_seen=1;first_time=$realtime-began;
        end
        if(!lr && slot==16 && measuring && !seen &&''')
source=source.replace('build/physical_latency.csv',(O/'physical_latency.csv').as_posix())
source=source.replace('timbre,pad,voltage_step_to_i2s_word_ns,threshold_abs_pcm','timbre,bank,pad,step_to_strike_ns,step_to_first_nonzero_i2s_ns,step_to_abs64_i2s_ns,threshold_abs_pcm')
source=source.replace('for(kind=0;kind<2;kind=kind+1)for(pad=0;pad<7;pad=pad+1)begin','''for(kind=0;kind<2;kind=kind+1)for(bank_case=0;bank_case<2;bank_case=bank_case+1)for(pad=0;pad<(bank_case==0 ? 1:7);pad=pad+1)begin
            bank=bank_case==0 ? 0:2;''')
a=source.index('            // Just miss');b=source.index('            while(!seen',a)
source=source[:a]+'''            // Step immediately after this pad's conversion latched the old
            // voltage: conservatively miss its aperture by one clock.
            @(negedge cs);
            while(dut.scanner.scan_channel!=pad)@(negedge cs);
            @(negedge clk);hit[pad]=1;seen=0;first_seen=0;strike_seen=0;measuring=1;began=$realtime;cycles=0;
'''+source[b:]
source=source.replace('$fdisplay(fd,"%0d,%0d,%0.3f,64",kind,pad,latency);',
    '$fdisplay(fd,"%0d,%0d,%0d,%0.3f,%0.3f,%0.3f,64",kind,bank,pad,strike_time,first_time,latency);')
source=source.replace('"latency timbre=%0d pad=%0d: %0.3f us",kind,pad,latency/1000',
    '"latency timbre=%0d bank=%0d pad=%0d: strike=%0.3f us first=%0.3f us abs64=%0.3f us",kind,bank,pad,strike_time/1000,first_time/1000,latency/1000')
source=source.replace('all 14 worst-scan-phase','all 16 worst-scan-phase')
if args.fallback:
    source=source.replace('.EARLY_FORCE_ENABLE(1)','.EARLY_FORCE_ENABLE(0)')
    source=source.replace('for(bank_case=0;','for(bank_case=1;').replace('pad<(bank_case==0 ? 1:7)','pad<1')
    source=source.replace('all 16 worst-scan-phase','both full peak-window fallback')
if args.all_octaves:
    source=source.replace('bank_case=1;','bank_case=0;').replace('bank_case<2','bank_case<5')
    source=source.replace('pad<(bank_case==0 ? 1:7)','pad<7').replace('pad<1;','pad<7;')
    source=source.replace('bank=bank_case==0 ? 0:2','bank=bank_case')
    source=source.replace('both full peak-window fallback','all 70 full peak-window fallback')
    source=source.replace('all 16 worst-scan-phase','all 70 octave/pad/timbre worst-scan-phase')
tb=O/'tb_physical_latency.v';tb.write_text(source,encoding='utf8')
source=source.replace('2200:1000',f'{args.pressed}:{args.baseline}')
source=source.replace('>=64',f'>={args.threshold}').replace('<=-64',f'<=-{args.threshold}')
source=source.replace(',64",kind',f',{args.threshold}",kind').replace('abs64',f'abs{args.threshold}').replace('64 counts',f'{args.threshold} counts')
tb.write_text(source,encoding='utf8')
files=[Path(n.get('path'))for n in ET.parse(F/'soundcore_speaker_omr_60k.gprj').findall('./FileList/File')if n.get('type')=='file.verilog' and Path(n.get('path')).name not in ['audio_pll_12m288.v','soundcore_melody_top.v','pressure_i2s_panel_oled_ble_experiment_top.v']]
bin=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');image=O/'latency.vvp'
sim_files=iverilog_sources(files,O/'simulation_sources',R)
c=subprocess.run([str(bin/'iverilog.exe'),'-g2012','-I',str(F),'-s','tb_physical_latency','-o',str(image),str(tb),*map(str,sim_files)],cwd=R,capture_output=True,text=True)
(O/'compile.log').write_text(c.stdout+c.stderr,encoding='utf8');assert c.returncode==0,c.stderr
with (O/'simulation.log').open('w',encoding='utf8')as log:
    p=subprocess.run([str(bin/'vvp.exe'),str(image)],cwd=R,stdout=log,stderr=subprocess.STDOUT,timeout=1200 if args.all_octaves else 240)
body=(O/'simulation.log').read_text(encoding='utf8');assert p.returncode==0 and 'PASS:'in body,body[-3000:]
import csv
rows=list(csv.DictReader((O/'physical_latency.csv').open()))
result={'source_build':str(F),'firmware':'0x00007B69'if F.name=='natural_seven_20261101'else 'candidate-not-programmed','cases':len(rows),'rate_hz':48000,'clock_hz':12288000,
    'spi_bit_clocks':13,'adc_frame_clocks':325,'eight_channel_scan_ms':2600/12288,
    'max_step_to_strike_ms':max(float(x['step_to_strike_ns'])for x in rows)/1e6,
    'max_step_to_first_nonzero_i2s_ms':max(float(x['step_to_first_nonzero_i2s_ns'])for x in rows)/1e6,
    f'max_step_to_abs{args.threshold}_i2s_ms':max(float(x[f'step_to_abs{args.threshold}_i2s_ns'])for x in rows)/1e6,
    'early_enabled':not args.fallback,'continuous_expression':True,'volume':16,'adc_baseline':args.baseline,'adc_pressed':args.pressed,'threshold_pcm_counts':args.threshold,
    'covers':('full 4-scan peak window forced; ' if args.fallback else '')+('both timbres, all seven pads across five octaves; worst ADC sample phase' if args.all_octaves else ('both timbres at C4; worst ADC sample phase' if args.fallback else 'both timbres, all seven pads at octave3, lowest C2 in both timbres; worst ADC sample phase')),
    'not_measured':['mechanical contact to sensor voltage','real ADC acquisition settling','MAX98357A analog/group delay','speaker/acoustic onset','real board jitter/noise'],
    'source_hashes':{str(p.relative_to(F)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files}}
(O/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items()if k!='source_hashes'},ensure_ascii=False,indent=2))
