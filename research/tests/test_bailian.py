from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import patch
import base64, io, json, tempfile, unittest, wave
from score_api.bailian import BailianConfig, NoRedirect, transcribe
from score_api.protocol import ApiError
from score_api.speech import backend_info, recognize


class FakeResponse(io.BytesIO):
    pass


class BailianTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'key'
        self.secret='sk-'+('x'*50)+'.'+('y'*62)
        self.path.write_text(self.secret,encoding='utf8')
        self.config=BailianConfig(str(self.path))
        out=io.BytesIO()
        with wave.open(out,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\x10\x00'*8000)
        self.wav=out.getvalue()

    def tearDown(self):self.temp.cleanup()

    def test_only_official_https_endpoints_and_synchronous_asr_models(self):
        for url in ['https://dashscope.aliyuncs.com/compatible-mode/v1','https://example-123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1']:
            BailianConfig(str(self.path),base_url=url).checked()
        for url in ['http://dashscope.aliyuncs.com/compatible-mode/v1','https://evil.example/compatible-mode/v1',
                    'https://dashscope.aliyuncs.com@evil.example/compatible-mode/v1','https://dashscope.aliyuncs.com/compatible-mode/v1?key=x']:
            with self.assertRaises(ApiError):BailianConfig(str(self.path),base_url=url).checked()
        for model in ['qwen-plus','qwen3-asr-flash-filetrans','qwen3-asr-flash-realtime']:
            with self.assertRaises(ApiError):BailianConfig(str(self.path),model=model).checked()
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://evil.example'))

    def test_realistic_key_punctuation_bom_and_no_header_injection(self):
        self.assertEqual(self.config.key(),self.secret)
        self.path.write_text('\ufeff'+self.secret+'\n',encoding='utf8')
        self.assertEqual(self.config.key(),self.secret)
        self.path.write_text(self.secret+'\r\nInjected: x',encoding='utf8')
        with self.assertRaises(ApiError):self.config.key()

    def test_request_is_audio_only_and_preserves_chinese_numeral_characters(self):
        seen=[]
        class Opener:
            def open(inner,req,timeout):
                seen.append(req)
                self.assertEqual(req.headers['Authorization'],'Bearer '+self.secret)
                self.assertNotIn(self.secret,req.data.decode())
                body=json.loads(req.data)
                self.assertEqual(body['asr_options'],{'language':'zh','enable_itn':False})
                self.assertEqual(len(body['messages']),1)
                encoded=body['messages'][0]['content'][0]['input_audio']['data'].split(',',1)[1]
                self.assertEqual(base64.b64decode(encoded),self.wav)
                return FakeResponse(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'我和我的祖国，一刻也不能分割！'}}],
                    'usage':{'total_tokens':218,'server_key':self.secret}}).encode())
        result=transcribe(self.wav,self.config,opener=Opener())
        self.assertEqual(result['text'],'我和我的祖国一刻也不能分割')
        self.assertEqual(result['usage'],{'total_tokens':218});self.assertEqual(len(seen),1)

    def test_error_does_not_echo_secret_and_has_no_paid_retry(self):
        seen=[]
        class Opener:
            def open(inner,req,timeout):
                seen.append(req)
                raise HTTPError(req.full_url,401,'error',{},FakeResponse(json.dumps({'error':{'code':'InvalidApiKey','message':self.secret}}).encode()))
        with self.assertRaises(ApiError) as raised:transcribe(self.wav,self.config,opener=Opener())
        self.assertNotIn(self.secret,str(raised.exception));self.assertEqual(raised.exception.code,'cloud_http_401')
        self.assertEqual(len(seen),1)

    def test_network_errors_are_safe_and_invalid_audio_never_requests(self):
        class Opener:
            def open(inner,req,timeout):raise URLError(self.secret)
        with self.assertRaises(ApiError) as raised:transcribe(self.wav,self.config,opener=Opener())
        self.assertNotIn(self.secret,str(raised.exception));self.assertEqual(raised.exception.code,'cloud_network')
        with self.assertRaises(ApiError):transcribe(b'not WAV',self.config,opener=Opener())

    def test_incomplete_empty_or_fractional_usage_is_not_accepted_as_truth(self):
        for response in [{'choices':[{'finish_reason':'length','message':{'content':'我'}}]},
                         {'choices':[{'message':{'content':'[noise]'}}]},
                         {'choices':[{'message':{'content':self.secret}}]}]:
            class Opener:
                def open(inner,req,timeout):return FakeResponse(json.dumps(response).encode())
            with self.assertRaises(ApiError):transcribe(self.wav,self.config,opener=Opener())

    def test_cloud_dispatch_does_not_import_the_local_qwen_asr_model(self):
        import numpy as np
        cfg={'speech':{'provider':'bailian','api_key_file':str(self.path)}}
        result={'text':'旋律','provider':'bailian','model':'qwen3-asr-flash','usage':{'total_tokens':20}}
        with patch('score_api.bailian.transcribe',return_value=result) as call:
            text,info=recognize(np.full(8000,.1,dtype=np.float32),cfg)
        self.assertEqual(text,'旋律');self.assertEqual(info['speech_provider'],'bailian')
        self.assertEqual(info['algorithm_id'],'source-vocal-units-v1-bailian')
        with wave.open(io.BytesIO(call.call_args.args[0]),'rb') as w:self.assertEqual(w.getnframes(),8000)
        self.assertEqual(backend_info({})['speech_provider'],'local')


if __name__=='__main__':unittest.main()
