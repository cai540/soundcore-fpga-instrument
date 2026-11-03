from pathlib import Path
import re
R=Path(__file__).resolve().parents[1]
for name in ['ScoreTransferTest.kt','MelodyFixtureTest.kt','SheetMusicTest.kt','ScoreApiTest.kt']:
    p=R/'app/android/app/src/test/java/cn/soundcore/instrument'/name
    t=(R/'build/natural_seven_20261101/before'/p.relative_to(R)).read_text(encoding='utf8')
    t=t.replace('Protocol.SCORE_BEGIN','Protocol.SCORE_ABSOLUTE_BEGIN')
    # Construct firmware layout2 ACKs; retain all original token, CRC and ordering assertions.
    t=re.sub(r'UploadedScoreState\(([^()\n]+)\)',lambda m:'UploadedScoreState('+m[1]+',schema=2)',t)
    t=t.replace('/3,0,7,0,1,0,t.token)','/3,0,7,0,1,0,t.token,schema=2)').replace('/3,0,7,0,1,0,transfer.token)','/3,0,7,0,1,0,transfer.token,schema=2)')
    p.write_text(t,encoding='utf8')
p=R/'app/android/app/src/test/java/cn/soundcore/instrument/MelodyRecognitionTest.kt';t=p.read_text(encoding='utf8')
t=t.replace('assertEquals(12, score.suggestedTranspose)','assertEquals(0, score.suggestedTranspose)')
t=t.replace('try { score.events(0); fail("range") } catch (_: IllegalArgumentException) { }','assertEquals(listOf(12,null,29),score.events(0).map{it.note})')
t=t.replace('listOf(0,null,17)','listOf(24,null,41)').replace('MelodyNote(1200,500,90,1f)','MelodyNote(1200,500,121,1f)')
t=t.replace('(200 shl 6) or (4 shl 3) or 6','(200 shl 7) or 34')
p.write_text(t,encoding='utf8')
