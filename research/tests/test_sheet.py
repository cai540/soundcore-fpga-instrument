from pathlib import Path
import hashlib,io,json,unittest
from PIL import Image
from score_api.sheet import compile_score,image_request,validate_sheet_result,VisionConfig
from score_api.protocol import ApiError

def sample():
    return {'notation':'jianpu','title':'测试','tonic_midi':62,'bpm':100,'numerator':4,'denominator':4,
        'measures':[{'id':1,'events':[{'degree':1,'ticks':96},{'degree':2,'ticks':96},{'degree':3,'ticks':192}]}],
        'play_order':[1],'warnings':[]}

class SheetTests(unittest.TestCase):
    def test_observed_real_vision_result_matches_independent_visible_sheet(self):
        case=json.loads((Path(__file__).parent/'fixtures/sheet_vision_observed.json').read_text(encoding='utf8'))
        result=compile_score(case['result']['score'])
        self.assertEqual([[e['start_ms'],e['duration_ms'],e['midi']] for e in result['events']],case['expected_events'])
        self.assertEqual(result['duration_ms'],12000)
    def test_independent_shared_vectors_match_android_pitch_clock_and_repeats(self):
        cases=json.loads((Path(__file__).parent/'fixtures/sheet_music_cases.json').read_text(encoding='utf8'))
        for case in cases:
            result=compile_score(case['score'])
            self.assertEqual([[e['start_ms'],e['duration_ms'],e['midi']] for e in result['events']],case['expected'],case['id'])
    def test_global_tick_clock_key_and_octave(self):
        s=sample();s['measures'][0]['events'][0].update(octave=1,accidental=-1)
        c=compile_score(s)
        self.assertEqual([n['midi'] for n in c['events']],[73,64,66]);self.assertEqual(c['duration_ms'],2400)
        self.assertEqual([n['duration_ms'] for n in c['events']],[600,600,1200])
    def test_rest_and_dotted_values_and_explicit_order(self):
        s=sample();s['measures'][0]['events']=[{'degree':0,'ticks':48},{'degree':5,'ticks':144},{'degree':1,'ticks':192}]
        s['play_order']=[1,1];c=compile_score(s)
        self.assertIsNone(c['events'][0]['midi']);self.assertEqual(c['duration_ms'],4800)
        self.assertEqual(c['events'][1]['duration_ms'],900)
    def test_tie_merges_only_identical_pitches_and_no_invented_attack(self):
        s=sample();s['measures'][0]['events']=[{'degree':1,'ticks':192,'tie_next':True},{'degree':1,'ticks':192}]
        self.assertEqual(len(compile_score(s)['events']),1)
        s['measures'][0]['events'][1]['degree']=2
        with self.assertRaises(ApiError):compile_score(s)
    def test_unmarked_tempo_is_disclosed_and_override_is_deterministic(self):
        s=sample();s['bpm']=None
        self.assertEqual(compile_score(s)['bpm'],80);self.assertTrue(compile_score(s)['warnings'])
        self.assertEqual(compile_score(s,120)['duration_ms'],2000)
    def test_bars_do_not_get_silently_padded_and_fractional_ticks_rejected(self):
        s=sample();s['measures'][0]['events'][0]['ticks']=48
        self.assertTrue(compile_score(s)['warnings']);self.assertEqual(compile_score(s)['duration_ms'],2100)
        s['measures'][0]['events'][0]['ticks']=48.5
        with self.assertRaises(ApiError):compile_score(s)
    def test_staff_uses_absolute_pitch_and_no_key_double_application(self):
        s=sample();s['notation']='staff';s['measures'][0]['events']=[{'midi':61,'ticks':384}]
        self.assertEqual(compile_score(s)['events'][0]['midi'],61)
    def test_invalid_repeat_and_wrong_source_are_rejected(self):
        s=sample();s['play_order']=[2]
        with self.assertRaises(ApiError):compile_score(s)
        with self.assertRaises(ApiError):validate_sheet_result({'schema_version':1,'request_id':'bad','source_sha256':'x','input_mode':'sheet','score':sample()},
            {'request_id':'good','source_sha256':'x','input_mode':'sheet'})
    def test_image_must_be_real_correct_type_size_and_digest(self):
        f=io.BytesIO();Image.new('RGB',(96,96),'white').save(f,format='PNG');body=f.getvalue();sha=hashlib.sha256(body).hexdigest()
        self.assertEqual(image_request(body,'image/png','a'*32,sha)['input_mode'],'sheet')
        for data,mime,digest in [(body,'image/jpeg',sha),(b'bad','image/png',''),(body,'image/png','wrong')]:
            with self.assertRaises(ApiError):image_request(data,mime,'a'*32,digest)
    def test_vision_does_not_allow_audio_model(self):
        VisionConfig('ignored').checked()
        with self.assertRaises(ApiError):VisionConfig('ignored',model='qwen3-asr-flash').checked()

if __name__=='__main__':unittest.main()
