"""Thirty sourced monophonic arrangements, preserving score timing and rests."""
from pathlib import Path
import sys,json,math,hashlib,shutil
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'build/product_repair_20261103/music_deps'))
import music21 as m
C=Path(m.__file__).parent/'corpus'
DEST=R/'app/android/app/src/main/assets/scores'
WEB=R/'web/phone-lab-20261030/public/scores'
EVIDENCE=R/'build/product_repair_20261103/catalog'
for p in (DEST,WEB,EVIDENCE/'originals'):p.mkdir(parents=True,exist_ok=True)
records=[]
def publish(id,title,events,bpm,category,composer,source,credit,original=None):
    ticks=sum(e['ticks'] for e in events)
    seconds=ticks*60/(96*bpm)
    repeats=1
    if seconds<60:
        repeats=math.ceil(75/seconds)
        events=events*repeats
    elif seconds>120:
        bpm=min(240,math.ceil(ticks*60/(96*105)))
    seconds=sum(e['ticks'] for e in events)*60/(96*bpm)
    assert 60<=seconds<=120,(id,seconds)
    assert len(events)<=1023,(id,len(events))
    credit+=f'；主旋律独奏编配，{bpm} BPM'+(f'，主题演奏{repeats}遍' if repeats>1 else '')
    obj=dict(schema='soundcore.score.v1',id=id,title=title,bpm=bpm,tonic=0,
             category=category,composer=composer,source=source,credit=credit,events=events)
    text=json.dumps(obj,ensure_ascii=False,separators=(',',':'))
    (DEST/(id+'.json')).write_text(text,encoding='utf8')
    (WEB/(id+'.json')).write_text(text,encoding='utf8')
    if original:shutil.copy2(original,EVIDENCE/'originals'/original.name)
    records.append(dict(id=id,title=title,composer=composer,category=category,
                        seconds=round(seconds,3),bpm=bpm,events=len(events),repeats=repeats,
                        credit=credit,source=source,file=id+'.json',url='https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site/scores/'+id+'.json',
                        sha256=hashlib.sha256(text.encode()).hexdigest()))

# Keep the three familiar project arrangements; make their repeats explicit.
for name in ('frere_jacques','ode_to_joy','twinkle'):
    old=json.loads((DEST/(name+'.json')).read_text('utf8'))
    publish(name,old['title'],old['events'],old['bpm'],'熟悉旋律',
            '贝多芬' if name=='ode_to_joy' else '传统旋律',
            'https://music21.org/music21docs/about/referenceCorpus.html',old.get('credit','项目传统旋律编配'))

def events_from(score):
    part=score.parts[0] if score.parts else score
    try:part=part.expandRepeats()
    except Exception:pass
    part=part.stripTies().flatten()
    events=[];cursor=0
    for n in sorted(part.notesAndRests,key=lambda n:float(n.offset)):
        a=round(float(n.offset)*96);z=round(float(n.offset+n.quarterLength)*96)
        if z<=cursor:continue
        a=max(a,cursor)
        if a>cursor:events.append(dict(midi=None,ticks=a-cursor))
        pitch=None if n.isRest else int(max(n.pitches,key=lambda p:p.midi).midi)
        if pitch is not None:assert 36<=pitch<=107
        duration=z-a
        while duration>0:
            step=min(1536,duration);events.append(dict(midi=pitch,ticks=step));duration-=step
        cursor=z
    # Breath at the theme boundary, including when explicitly repeated.
    events.append(dict(midi=None,ticks=96))
    return events

bach=['bwv1.6','bwv10.7','bwv101.7','bwv102.7','bwv103.6','bwv104.6','bwv108.6',
      'bwv11.6','bwv110.7','bwv111.6','bwv113.8','bwv114.7','bwv115.6','bwv116.6','bwv117.4']
for name in bach:
    original=C/'bach'/(name+'.mxl');score=m.converter.parse(original)
    title='巴赫 · 圣咏 '+name.replace('bwv','BWV ')
    source='https://github.com/cuthbertLab/music21/blob/master/music21/corpus/bach/'+name+'.mxl'
    publish('bach_'+name.replace('.','_'),title,events_from(score),72,'古典','J. S. 巴赫',source,
            '公版作品；music21语料编码，取女高音主旋律',original)

original=C/'airdsAirs/book1.abc';book=m.converter.parse(original)
chosen=[0,2,4,8,9,11,13,17,19,20,22,24]
chinese=['高地人的歌','村庄的伙伴','淑女的游戏','月亮与七颗星','盛大行进','红心皇后',
         '爱尔兰双簧管','无论如何','欢乐时光','坎贝尔人来了','威克洛的矿工','兰戈·李']
for index,title in zip(chosen,chinese):
    score=list(book.scores)[index]
    source='https://github.com/cuthbertLab/music21/blob/master/music21/corpus/airdsAirs/book1.abc'
    publish('airds_1_'+str(index+1),title,events_from(score),108,'民间旋律','传统 · Aird选集',source,
            '18世纪传统旋律，Aird第一册；原题：'+score.metadata.title,original)
assert len(records)==30 and len({r['id'] for r in records})==30
(WEB/'catalog.json').write_text(json.dumps(dict(schema='soundcore.catalog.v1',scores=records),ensure_ascii=False,indent=2),encoding='utf8')
(EVIDENCE/'catalog_sources.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(C/'license.txt',EVIDENCE/'music21-corpus-license.txt')
print(json.dumps(dict(scores=len(records),min_seconds=min(x['seconds']for x in records),max_seconds=max(x['seconds']for x in records),max_events=max(x['events']for x in records)),ensure_ascii=False))
