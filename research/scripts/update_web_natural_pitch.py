from pathlib import Path
R=Path(__file__).resolve().parents[1];p=R/'web/phone-lab-20261030/app/page.tsx';t=p.read_text(encoding='utf8')
t=t.replace('noteName,padFor,splitParts','noteName,padFor,naturalMidi,splitParts')
t=t.replace('[bank,setBank]=useState(0)','[bank,setBank]=useState(2),[tonicKey,setTonicKey]=useState(0)')
t=t.replace('padFor(e.midi+transpose)','padFor(e.midi+transpose,tonicKey)').replace('padFor(expected.midi!+transpose)','padFor(expected.midi!+transpose,tonicKey)').replace('padFor(target.midi!+transpose)','padFor(target.midi!+transpose,tonicKey)')
t=t.replace('(e.midi+transpose-60)/7','(e.midi+transpose-36-tonicKey)/12').replace('(n.midi!+transpose-60)/7','(n.midi!+transpose-36-tonicKey)/12').replace('(notes[next].midi!+transpose-60)/7','(notes[next].midi!+transpose-36-tonicKey)/12')
t=t.replace('60+bank*7+pad','naturalMidi(bank,pad,tonicKey)').replace('60+bank*7+i','naturalMidi(bank,i,tonicKey)')
needle='  const pads=<div'
t=t.replace(needle,'''  const keySelector=<label className="range-label">调号<select aria-label="演奏调号" value={tonicKey} disabled={phase!=='idle'} onChange={e=>{stop();setTonicKey(+e.target.value)}}>{['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'].map((name,index)=><option key={index} value={index}>{name} 大调</option>)}</select><span>1—7 自然音 · 音区按八度切换</span></label>;
  const pads=<div''')
# Place a single selector with the performance keyboard.
t=t.replace("{tab==='play'&&<>","{tab==='play'&&<>{keySelector}")
assert 'bank*7'not in t and '-60)/7'not in t
p.write_text(t,encoding='utf8')
