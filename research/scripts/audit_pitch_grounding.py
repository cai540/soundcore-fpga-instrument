"""Reference-based error discovery and direct waveform checks; diagnostic only."""
from pathlib import Path
import csv,json,subprocess
import numpy as np
from scipy.signal import find_peaks
from evaluate_oss_vocals import read_notes,track
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';B.mkdir(exist_ok=True)
PRE=R/'build/vocal_syllable_main_20261029';OSS=R/'build/vocal_oss_20261029'

def main():
    summary=[];details=[]
    for name,ref in [('zuguo','wodezuguo'),('chilege','chilege'),('qiansixi','qiansixi')]:
        info=json.loads((PRE/name/'full/result.json').read_text());pcm=np.fromfile(info['input_file'],dtype='<f4')
        ns=read_notes(PRE/name/'full/notes.csv');p=track(ns,info['source_ms'])
        ev=dict(np.load(PRE/name/'full/evidence.npz'))
        source=R/'songs/source'/(ref+'_vocals_20261026'+('.wav' if name=='chilege' else '.mp3'))
        stereo=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-ar','16000','-ac','2','-f','f32le','-']),dtype='<f4').reshape(-1,2)
        refs=list(csv.DictReader((R/f'songs/product_song_review/{ref}.csv').open(encoding='utf8')))
        bad=[]
        for q in refs:
            target=int(q['source_midi'])
            if target<=0:continue
            a=int(np.ceil((float(q['source_start_s'])+.12)*100));z=int(np.floor((float(q['source_end_s'])-.12)*100))
            if z<=a:continue
            predicted=p[a:z];wrong=(predicted>0)&(predicted!=target)
            if np.mean(wrong)<.5:continue
            center=round((a+z)*5);k=center//10
            samples=pcm[max(0,center*16-2048):center*16+2048]
            spectrum=np.abs(np.fft.rfft(samples*np.hanning(len(samples)),n=32768))
            peaks,_=find_peaks(spectrum,distance=20)
            peaks=sorted(peaks,key=lambda x:spectrum[x],reverse=True)[:8]
            wave_peaks=[{'hz':round(float(i*16000/32768),2),'midi':round(float(69+12*np.log2(max(1,i*16000/32768)/440)),2),
                         'relative_amp':round(float(spectrum[i]/spectrum.max()),3)} for i in peaks]
            a0=max(0,center*16-4000);z0=min(len(stereo),center*16+4000);s=stereo[a0:z0]
            mono=s.mean(axis=1);old=pcm[a0:z0]
            corr=float(np.corrcoef(old,mono)[0,1]);lr=float(np.corrcoef(s[:,0],s[:,1])[0,1])
            row={'name':name,'center_source_ms':center,'start_source_ms':a*10,'end_source_ms':z*10,
                 'reference':target,'output_mode':int(np.bincount(predicted[predicted>0]).argmax()) if np.any(predicted>0) else 0,
                 'rmvpe_midi':round(float(69+12*np.log2(max(1,ev['rmvpe'][k])/440)),2),
                 'fcpe_midi':round(float(69+12*np.log2(max(1,ev['fcpe'][k])/440)),2),'wave_peaks':wave_peaks,
                 'source_mono_pcm_correlation':round(corr,4),'stereo_lr_correlation':round(lr,4)}
            bad.append(row)
        details+=bad
        summary.append({'name':name,'error_intervals':len(bad),'semitone':sum(abs(v['output_mode']-v['reference'])==1 for v in bad),
                        'octave':sum(abs(v['output_mode']-v['reference'])==12 for v in bad),
                        'other':sum(abs(v['output_mode']-v['reference']) not in [1,12] for v in bad)})
    (B/'pitch_error_spots.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf8')
    (B/'pitch_error_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    for q in details[:14]:print(json.dumps(q,ensure_ascii=False))

if __name__=='__main__':main()
