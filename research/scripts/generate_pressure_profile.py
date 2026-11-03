from pathlib import Path
import argparse,hashlib,json,zlib,re
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--profile',default='config/pressure_profile_v1.json')
parser.add_argument('--artifact-dir',default='build/early_pressure_20261028')
args=parser.parse_args()
PROFILE=ROOT/args.profile
p=json.loads(PROFILE.read_text(encoding='utf-8'))
assert p['schema_version'] in (1,2) and len(p['channel_gain_q8'])==7
assert all(0<=x<=512 for x in p['channel_gain_q8'])
input_scales=p.get('channel_input_scale_q12',[4096]*7)
assert len(input_scales)==7 and all(isinstance(x,int) and 2048<=x<=8192 for x in input_scales)
calibrated=any(x!=4096 for x in input_scales)
segments=p['curve_segments'];assert segments[-1]['upper_exclusive']==4096
assert [s['upper_exclusive'] for s in segments]==sorted(s['upper_exclusive'] for s in segments)
policy=p['early_policy'];assert 1<=policy['settled_follow_samples']<=3 and 0<=policy['peak_margin_codes']<=1024
canonical=json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
profile_id=zlib.crc32(canonical)&0xffffffff
config=f'''// Generated from {PROFILE.relative_to(ROOT).as_posix()}. Do not hand-edit.
`ifndef SOUNDCORE_PRESSURE_PROFILE_CONFIG
`define SOUNDCORE_PRESSURE_PROFILE_CONFIG
`define SC_PRESSURE_PROFILE_ID 32'h{profile_id:08x}
`define SC_PRESSURE_EARLY_FOLLOW {policy['settled_follow_samples']}
`define SC_PRESSURE_EARLY_MARGIN 12'd{policy['peak_margin_codes']}
`endif
'''
(ROOT/'rtl/pressure_profile_config.vh').write_text(config,encoding='utf-8')
lines=['// Generated accepted fixed-point response; stored in FPGA configuration.',
 'function [7:0] pressure_velocity;','    input [11:0] force_code;',
 '    reg [11:0] delta;','    reg [7:0] base_level;','    reg [10:0] slope;',
 '    reg [18:0] scaled;','    begin']
for i,s in enumerate(segments):
    cond=('if' if i==0 else 'else if')+f" (force_code < 12'd{s['upper_exclusive']})" if s['upper_exclusive']<4096 else 'else'
    lines.append('        '+cond+' begin')
    lines.append(f"            base_level=8'd{s['base']};")
    lines.append(f"            delta=force_code-12'd{s['origin']};" if s['slope_q10'] else "            delta=0;")
    lines.append(f"            slope=11'd{s['slope_q10']};")
    lines.append('        end')
lines+=['        scaled=delta*slope;','        pressure_velocity=base_level+scaled[17:10];','    end','endfunction',
 'function [9:0] pressure_gain_q8;','    input [2:0] channel;','    begin','        case(channel)']
for i,g in enumerate(p['channel_gain_q8']):lines.append(f"            3'd{i}: pressure_gain_q8=10'd{g};")
lines+=['            default: pressure_gain_q8=10\'d256;','        endcase','    end','endfunction']
if calibrated:
    lines+=['// Normalize the zero-subtracted ADC span BEFORE the nonlinear curve.',
            'function [13:0] pressure_input_scale_q12;',
            '    input [2:0] channel;','    begin','        case(channel)']
    for i,g in enumerate(input_scales):lines.append(f"            3'd{i}: pressure_input_scale_q12=14'd{g};")
    lines+=['            default: pressure_input_scale_q12=14\'d4096;',
            '        endcase','    end','endfunction',
            'function [11:0] normalized_pressure;',
            '    input [2:0] channel;','    input [11:0] force_code;',
            '    reg [25:0] scaled_force;', '    begin',
            "        scaled_force=force_code*pressure_input_scale_q12(channel)+26'd2048;",
            "        normalized_pressure=scaled_force[25:12]>14'd4095 ? 12'd4095 : scaled_force[23:12];",
            '    end','endfunction']
curve_input='normalized_pressure(channel,force_code)' if calibrated else 'force_code'
lines+=[
 'function [7:0] pad_velocity;','    input [2:0] channel;','    input [11:0] force_code;',
 '    reg [17:0] scaled_level;','    begin',
 f'        scaled_level=pressure_velocity({curve_input})*pressure_gain_q8(channel);',
 "        pad_velocity=scaled_level[17:8]>10'd255 ? 8'd255 : scaled_level[15:8];",'    end','endfunction','']
curve='\n'.join(lines)
(ROOT/'rtl/pressure_profile_curve.vh').write_text(curve,encoding='utf-8')
# Embed generated constants directly so older projects and both compilers do
# not depend on compiler-specific absolute include-path conventions.
detector=ROOT/'rtl/fsr_strike_detector.v'
source=detector.read_text(encoding='utf-8')
start='// BEGIN GENERATED PRESSURE PROFILE'
end='// END GENERATED PRESSURE PROFILE'
block=start+'\n    localparam [31:0] PRESSURE_PROFILE_ID=32\'h'+f'{profile_id:08x}'+';\n'+curve+'\n    '+end
if start in source:
    a=source.index(start);z=source.index(end,a)+len(end);source=source[:a]+block+source[z:]
else:
    token='`include "D:/FPGA/Projects/soundcore_2026/rtl/pressure_profile_curve.vh"'
    assert token in source;source=source.replace(token,block)
source=re.sub(r'parameter integer EARLY_MIN_FOLLOW = [^,]+,',f"parameter integer EARLY_MIN_FOLLOW = {policy['settled_follow_samples']},",source)
source=re.sub(r"parameter \[11:0\] EARLY_PEAK_MARGIN = [^,]+,",f"parameter [11:0] EARLY_PEAK_MARGIN = 12'd{policy['peak_margin_codes']},",source)
if detector.read_text(encoding='utf-8')!=source:detector.write_text(source,encoding='utf-8')
out=ROOT/args.artifact_dir;out.mkdir(parents=True,exist_ok=True)
values=[]
for code in range(4096):
    s=next(s for s in segments if code<s['upper_exclusive'])
    delta=code-s['origin'] if s['slope_q10'] else 0
    values.append((s['base']+(((delta*s['slope_q10'])&0x7ffff)>>10))&255)
assert all(a<=b for a,b in zip(values,values[1:]))
(out/'saved_curve.mem').write_text('\n'.join(f'{x:02x}' for x in values)+'\n')
if calibrated:
    expected=[]
    for channel,scale in enumerate(input_scales):
        for code in range(4096):
            normalized=min(4095,(code*scale+2048)//4096)
            expected.append(min(255,values[normalized]*p['channel_gain_q8'][channel]//256))
    (out/'expected_pad_velocity.mem').write_text('\n'.join(f'{x:02x}' for x in expected)+'\n')
(out/'profile_manifest.json').write_text(json.dumps({'profile_id':f'{profile_id:08x}',
    'profile_sha256':hashlib.sha256(PROFILE.read_bytes()).hexdigest(),
    'requires_manual_calibration_each_boot':False,'dynamic_training_performed':False,
    'curve_values':4096,'channel_input_scale_q12':input_scales,'calibrated_mapping_values':28672 if calibrated else 0,'generated_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
      ['rtl/pressure_profile_config.vh','rtl/pressure_profile_curve.vh']}},indent=2),encoding='utf-8')
print(f'Saved profile {profile_id:08x}; 4096 monotone curve entries; no manual boot calibration.')
