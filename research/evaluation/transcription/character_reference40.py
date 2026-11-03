"""Score-only character carriers for the requested one/two-note rendition.

This is a separate evaluation target, not a replacement for the old expanded
score-note metric. Source locators are coarse, not millisecond timing gold.
No runtime observer/decoder imports this file.
"""
from pathlib import Path
import hashlib,json

def main():
    cases=[]
    def line(text,carriers,span):
        assert len(text)==len(carriers),(text,len(text),len(carriers))
        units=[]
        for char,value in zip(text,carriers):
            # A tuple explicitly lists the score's ordered within-character
            # movement. Either one of its real tones is a legal reduction.
            pitches=[value] if isinstance(value,int) else list(value)
            assert 1<=len(pitches)<=2
            choices=[[p] for p in pitches]
            if len(pitches)==2:choices.append(pitches)
            units.append({'character':char,'allowed_sequences':choices})
        return {'text':text,'source_span_s':span,'units':units}
    z=[
        line('我和我的祖国',[72,(74,72),(70,69),67,65,60],[47.1,52.1]),
        line('一刻也不能分割',[65,69,77,76,74,69,72],[52.2,57.4]),
        line('无论我走到哪里',[74,(76,74),72,70,69,67,62],[57.4,62.5]),
        line('都流出一首赞歌',[64,62,60,72,65,67,69],[62.6,67.7]),
        line('我歌唱每一座高山',[72,74,72,70,69,67,65,60],[67.7,72.9]),
        line('我歌唱每一条河',[65,69,77,76,79,77,74],[73.,78.2]),
        line('袅袅炊烟',[77,76,74,72],[78.2,80.8]),
        line('小小村落',[74,72,70,69],[80.9,83.5]),
    ]
    q=[
        line('嘲笑谁恃美扬威',[65,64,60,60,57,60,62],[24.1,29.4]),
        line('没了心如何相配',[65,64,60,60,57,67,69],[29.5,34.2]),
        line('盘铃声清脆帷幕间灯火幽微',[69,72,67,69,67,65,64,65,64,65,67,69],[34.4,40.3]),
        line('我和你最天生一对',[67,69,62,67,69,62,60,62],[40.3,46.]),
        line('没了你才算原罪',[65,64,60,60,57,60,62],[46.2,51.2]),
        line('没了心才好相配',[65,64,60,60,57,67,69],[51.5,56.5]),
        line('你褴褛我彩绘并肩行过山与水',[69,72,67,69,(72,67),67,65,64,65,64,65,67,69],[56.5,62.5]),
    ]
    c=[
        line('心随天地走',[64,66,59,66,64],[31.2,33.7]),
        line('意被牛羊牵',[64,66,59,57,54],[33.7,38.]),
        line('大漠的孤烟',[64,66,59,66,64],[38.6,41.4]),
        line('拥抱落日圆',[64,66,69,71,(71,66)],[41.4,45.5]),
        line('在天的尽头',[66,69,71,69,66],[46.,48.7]),
        line('与月亮聊天',[64,66,69,64,(59,62)],[48.7,53.]),
        line('篝火映着脸',[64,66,59,66,64],[53.4,56.1]),
        line('醉了套马杆',[64,66,59,57,(57,59)],[56.1,60.7]),
        line('心随天地走',[64,66,59,66,64],[61.5,63.9]),
        line('寻找那达观',[64,66,69,(64,66),66],[63.9,69.]),
    ]
    for name,offset,phrases,score in [('zuguo',43.5,z,'wodezuguo_score_20261026.jpg'),('qiansixi',22.5,q,'qiansixi_numbered_score_2026-10-26.jpg'),('chilege',29.,c,'chilege_score_20261026.jpg')]:
        cases.append({'id':name,'source_offset_s':offset,'duration_s':40,'phrases':phrases,
            'source_score':str(Path('songs/source')/score),'source_score_sha256':hashlib.sha256(Path('songs/source',score).read_bytes()).hexdigest()})
    out={'metric_target':'character-carrier-reduction-v1','pitch_and_octave_exact':True,
        'interpretation':'Each lyric character must have one score-supported carrier, optionally its ordered second score tone; no tolerance in semitones/octaves. This measures the requested reduced playable melody, not note-for-note restoration or rhythm accuracy.',
        'timing_gold_available':False,'text_is_evaluation_only':True,'cases':cases}
    Path('evaluation/transcription/character_reference40.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
    print([(c['id'],sum(len(p['units']) for p in c['phrases'])) for c in cases])

if __name__=='__main__':main()
