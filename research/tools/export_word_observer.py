"""One-time export of a released RWBD observer; not a runtime dependency.

Usage requires an upstream ROSVOT checkout, checkpoint and its YAML config.
Only the original network logits and exact frontend parameters are exported.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    import torch
    import yaml
    from modules.rosvot.rosvot import WordbdExtractor
    from utils.commons.ckpt_utils import load_ckpt
    from utils.commons.hparams import hparams
    from utils.audio.mel import MelNet
    torch.set_num_threads(6)
    torch.manual_seed(0)
    config = yaml.safe_load(args.config.read_text(encoding='utf8'))
    hparams.clear()
    hparams.update(config)
    word = WordbdExtractor(config).eval()
    load_ckpt(word, str(args.checkpoint), verbose=False)

    class Observer(torch.nn.Module):
        def __init__(self, network):
            super().__init__()
            self.network = network

        def forward(self, mel, pitch, uv):
            net = self.network
            features = net.run_encoder(mel=mel, pitch=pitch, uv=uv)
            features = net.net(features)
            logits = net.word_bd_out(features).squeeze(-1) / net.word_bd_temperature
            return torch.clamp(logits, -16, 16).sigmoid()

    observer = Observer(word).eval()
    args.output.mkdir(parents=True, exist_ok=True)
    mel = torch.randn(1, 256, config['use_mel_bins'])
    pitch = torch.full((1, 256), 120, dtype=torch.long)
    uv = torch.zeros_like(pitch)
    path = args.output / 'word_boundary.onnx'
    torch.onnx.export(observer, (mel, pitch, uv), str(path), opset_version=17, dynamo=False,
        input_names=['mel', 'pitch', 'uv'], output_names=['probability'],
        dynamic_axes={name: {0: 'B', 1: 'T'} for name in ['mel', 'pitch', 'uv', 'probability']})
    frontend = MelNet(config)
    np.savez_compressed(args.output / 'frontend.npz', mel=frontend.mel_basis.numpy(),
                        hann=frontend.hann_window.numpy())
    import onnxruntime as ort
    session = ort.InferenceSession(str(path), providers=['CPUExecutionProvider'])
    parity = []
    with torch.inference_mode():
        for count in (128, 256, 512):
            x = torch.randn(1, count, config['use_mel_bins'])
            p = torch.full((1, count), 100, dtype=torch.long)
            u = torch.zeros_like(p)
            expected = observer(x, p, u).numpy()
            actual = session.run(None, {'mel': x.numpy(), 'pitch': p.numpy(), 'uv': u.numpy()})[0]
            error = float(np.max(abs(expected - actual)))
            if error > 1e-4:
                raise AssertionError('Word network export changed output')
            parity.append({'frames': count, 'max_absolute_error': error})
    manifest = {'checkpoint_sha256': hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        'onnx_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'parity': parity,
        'sample_rate': config['audio_sample_rate'], 'fft_size': config['fft_size'],
        'hop_size': config['hop_size'], 'win_size': config['win_size'],
        'use_mel_bins': config['use_mel_bins'], 'pitch_bins': 256, 'pitch_min_hz': 50.,
        'pitch_max_hz': 900., 'frontend_sha256': hashlib.sha256((args.output / 'frontend.npz').read_bytes()).hexdigest(),
        'source': 'ROSVOT WordbdExtractor, original pretrained weights, no retraining',
        'lyrics_or_song_identity_used': False}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    print(json.dumps(parity), flush=True)


if __name__ == '__main__':
    main()
