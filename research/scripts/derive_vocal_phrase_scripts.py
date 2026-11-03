"""Prepare bounded 0.8 verification scripts from the audited 0.7 workflow."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/'scripts/compare_vocal_natural.py').read_text(encoding='utf8')
s=s.replace("B=ROOT/'build/vocal_natural_20261029'","B=ROOT/'build/vocal_phrase_20261029'").replace("OLD=ROOT/'build/vocal_refine_20261029/audio'","OLD=ROOT/'build/vocal_natural_20261029/audio'")
s=s.replace('DumpVocalFrontEnd','DumpVocalPhraseStages')
(R/'scripts/compare_vocal_phrase.py').write_text(s,encoding='utf8')
s=(R/'scripts/summarize_vocal_natural.py').read_text(encoding='utf8').replace('vocal_natural_20261029','vocal_phrase_20261029')
(R/'scripts/summarize_vocal_phrase.py').write_text(s,encoding='utf8')
s=(R/'scripts/evaluate_vocal_natural.py').read_text(encoding='utf8').replace("BASE=ROOT/'build/vocal_refine_20261029/audio'","BASE=ROOT/'build/vocal_natural_20261029/audio'")
(R/'scripts/evaluate_vocal_phrase.py').write_text(s,encoding='utf8')
s=(R/'scripts/verify_vocal_natural.py').read_text(encoding='utf8')
s=s.replace("B=ROOT/'build/vocal_natural_20261029'","B=ROOT/'build/vocal_phrase_20261029'")
s=s.replace("test_count==143","test_count>=178")
s=s.replace("ROOT/'build/vocal_refine_20261029/frozen_classes'","ROOT/'build/vocal_natural_20261029/frozen_classes'")
s=s.replace("stages['seed']==read(old/'notes.csv')","stages['seed']==read(old/'stage_seed.csv')")
s=s.replace("'0.6 seed changed: '","'0.7 seed changed: '")
# 0.8 may intentionally project an uncertain release, retaining sounding union.
# Provenance of newly restored cuts is audited separately against recovery output.
s=s.replace("assert (restored_starts-original_starts)<=final_starts,'Recovered boundary removed'","assert (restored_starts-original_starts)<=final_starts,'0.7 recovered boundary removed'")
s=s.replace("fromfile='0.6/'","fromfile='0.7/'").replace("tofile='0.7/'","tofile='0.8/'")
s=s.replace("expected={'app/android/app/build.gradle.kts','app/android/app/src/main/java/cn/soundcore/instrument/MelodyRecognition.kt'}","expected={'app/android/app/build.gradle.kts',*['app/android/app/src/main/java/cn/soundcore/instrument/'+n+'.kt' for n in ['MelodyRecognition','VocalMainNoteSegmentation']]}")
s=s.replace("helpers=['VocalBoundaryEvidence','VocalEventRestoration','TonalPitchRefinement','TonalBoundaryCoalescing','VocalNaturalRefinement']","helpers=['VocalOctaveValidation','ReleaseContourProjection','VocalAlternativeRestoration']")
s=s.replace("B/'baseline/build/vocal_refine_20261029/release.json'","B/'baseline/build/vocal_natural_20261029/release.json'")
s=s.replace("'Published 0.6 APK changed'","'Published 0.7 APK changed'")
s=s.replace("metadata['versionCode']==7 and metadata['versionName']=='0.7-natural-melody'","metadata['versionCode']==8 and metadata['versionName']=='0.8-vocal-phrases'")
s=s.replace("'previous_06_apk'","'previous_07_apk'").replace("'algorithm_version':5","'algorithm_version':6")
(R/'scripts/verify_vocal_phrase.py').write_text(s,encoding='utf8')
print('Prepared compare/summarize/evaluate/verify for 0.8; review all generated changes before run.')
