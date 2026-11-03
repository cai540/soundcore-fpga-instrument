from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];A=R/'app/android/app/src/main/assets/scores';A.mkdir(exist_ok=True)
catalog=[]
def song(id,title,bpm,phrases):
 events=[]
 for phrase in phrases:
  for note,duration in phrase:events.append(dict(midi=note,ticks=duration))
  events.append(dict(midi=None,ticks=48))
 score=dict(schema='soundcore.score.v1',id=id,title=title,bpm=bpm,tonic=0,credit='传统旋律 / 公版主题 · 声芯项目独奏编配',events=events)
 p=A/(id+'.json');p.write_text(json.dumps(score,ensure_ascii=False,indent=2),encoding='utf8');catalog.append(dict(id=id,title=title,file=p.name))
def line(notes):
 return [(60+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[t[0]],int(t[1:]) if len(t)>1 else 96)for t in notes.split()]
song('twinkle','小星星',112,list(map(line,['C C G G A A G192','F F E E D D C192','G G F F E E D192','G G F F E E D192','C C G G A A G192','F F E E D D C192'])))
song('frere_jacques','两只老虎',112,list(map(line,['C D E C C D E C','E F G192 E F G192','G48 A48 G48 F48 E C G48 A48 G48 F48 E C','C G C192 C G C192'])))
song('ode_to_joy','欢乐颂',110,list(map(line,['E E F G G F E D','C C D E E144 D48 D192','E E F G G F E D','C C D E D144 C48 C192'])))
(R/'build/acceptance_20261102/catalog.json').write_text(json.dumps(dict(schema='soundcore.catalog.v1',scores=catalog),ensure_ascii=False,indent=2),encoding='utf8')
print('Generated',len(catalog),'bounded score data files')
