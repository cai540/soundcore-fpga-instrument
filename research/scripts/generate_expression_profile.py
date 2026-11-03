from pathlib import Path
import argparse,hashlib,json,re,zlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--profile',default='config/expression_profile_v2.json')
parser.add_argument('--artifact-dir',default='build/timbre_pressure_repair_20261101/expression')
parser.add_argument('--allow-legacy35-overwrite',action='store_true',help='Explicitly permit replacing existing72-note data with historical35-note tables')
args=parser.parse_args();OUT=ROOT/args.artifact_dir;OUT.mkdir(parents=True,exist_ok=True)
if not args.allow_legacy35_overwrite and any((ROOT/'rtl'/name).exists()and len((ROOT/'rtl'/name).read_text().split())==1296 for name in ['expression_normalized.mem','expression_raw.mem']):
    parser.error('Historical35-note generator cannot overwrite72-note tone data. Use generate_harmonica_profile_20261102.py; legacy reproduction requires --allow-legacy35-overwrite.')
P=ROOT/args.profile;p=json.loads(P.read_text(encoding='utf-8'))
assert p['schema_version']==1 and p['sample_rate_hz']==48000
assert 0<p['control_interval_frames']<256 and 0<p['slew_up']<16 and 0<p['slew_down']<16
assert isinstance(p['quiet_texture_shift'],int) and 14<=p['quiet_texture_shift']<=20

def sine(phase):
    phase=np.asarray(phase,dtype=np.uint64)&0xffffffff;q=(phase+0x40000000)&0xffffffff
    t=np.where(q>>31,((~(q>>16))&32767)*2,((q>>16)&32767)*2).astype(np.int64)
    # Same signed17-bit construction as instrument_texture.sine.
    x=(t^32768)+np.where(t<32768,65536,0);x=np.where(x>=65536,x-131072,x)
    return (x*(65536-np.abs(x)))>>15

phase=np.arange(8192,dtype=np.uint64)*(2**32//8192)
waves=np.array([sine(phase*k) for k in range(1,7)],dtype=float)
tables={};analysis=[]
for timbre in range(2):
    kind='harmonica' if timbre else 'erhu'
    for note in range(35):
        f0=440*2**((60+note-69)/12);freq=f0*np.arange(1,7)
        body=p.get(kind+'_body',dict(floor=.8 if timbre else .7,peak=.35 if timbre else .55,
            centre_hz=1200 if timbre else 1700,width_octaves=.9 if timbre else .7,rolloff_hz=22000 if timbre else 18000))
        shape=(body['floor']+body['peak']*np.exp(-.5*(np.log2(freq/body['centre_hz'])/body['width_octaves'])**2))*np.exp(-freq/body['rolloff_hz'])
        for anchor in range(9):
            x=anchor/8;weights=((1-x)*np.array(p[kind+'_soft'])+x*np.array(p[kind+'_strong']))*shape
            raw=weights*p['raw_weight_scale'];sig=raw@waves
            norm=raw*p['target_wave_rms']/np.sqrt(np.mean(sig*sig))
            assert norm.sum()*32768<15000 and max(norm)<.9
            values={0:np.rint(raw*4096).astype(int),1:np.rint(norm*4096).astype(int)}
            for mode,w in values.items():
                assert np.all((w>=0)&(w<4096));tables[(mode,timbre,note,anchor)]=w
            analysis.append(dict(timbre=timbre,note=note,anchor=anchor,
                normalized_rms=float(np.sqrt(np.mean(((values[1]/4096)@waves)**2)))))
# Dual synchronous reads fit ROM prefetch into the existing phase stage.
for mode,name in [(0,'expression_raw.mem'),(1,'expression_normalized.mem')]:
    packed=[]
    for timbre in range(2):
        for note in range(35):
            for anchor in range(9):
                n=0
                for v in reversed(tables[(mode,timbre,note,anchor)]):n=(n<<12)|int(v)
                packed.append(f'{n:018x}')
    target=ROOT/'rtl'/name;content='\n'.join(packed)+'\n'
    if not target.exists() or target.read_text()!=content:target.write_text(content)
controller=ROOT/'rtl/pressure_expression32.v';text=controller.read_text()
for param,field in [('ATTACK_HOLD_FRAMES','attack_hold_frames'),('CONTROL_INTERVAL','control_interval_frames'),
    ('DEADBAND','deadband'),('SLEW_UP','slew_up'),('SLEW_DOWN','slew_down')]:
    text=re.sub(r'(parameter integer '+param+r'=)\d+',lambda m:m[1]+str(p[field]),text)
if controller.read_text()!=text:controller.write_text(text)
texture=ROOT/'rtl/expressive_texture.v';text=texture.read_text(encoding='utf-8')
text,count=re.subn(r'(parameter integer TEXTURE_SHIFT=)\d+',lambda m:m[1]+str(p['quiet_texture_shift']),text)
assert count==1,'The expressive source must expose its stored texture gain'
texture.write_text(text,encoding='utf-8')
(OUT/'profile_validation.json').write_text(json.dumps({'profile_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),
    'profile_id':f'{zlib.crc32(P.read_bytes()):08x}','parameter_source':p['provenance'],
    'anchor_count':len(analysis),'reference_rms_min':min(x['normalized_rms'] for x in analysis),
    'reference_rms_max':max(x['normalized_rms'] for x in analysis),'manual_boot_calibration':False,
    'generated_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['rtl/pressure_expression32.v','rtl/expressive_texture.v','rtl/expression_normalized.mem','rtl/expression_raw.mem']}},indent=2))
(OUT/'coefficient_reference.json').write_text(json.dumps({','.join(map(str,k)):v.tolist() for k,v in tables.items()}))
print('Saved expression profile;630 pitch/timbre/expression anchors; no recorded PCM.')
