"""Export original RMVPE acoustic observations, without note corrections."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    import torch
    from modules.pe.rmvpe.model import E2E0
    from modules.pe.rmvpe.spec import MelSpectrogram
    from modules.pe.rmvpe.constants import N_MELS, SAMPLE_RATE, WINDOW_LENGTH, MEL_FMIN, MEL_FMAX
    torch.set_num_threads(6)
    torch.manual_seed(0)
    model = E2E0(4, 1, (2, 2)).eval()
    checkpoint = torch.load(str(args.checkpoint), map_location='cpu')
    model.load_state_dict(checkpoint['model'], strict=True)
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / 'pitch.onnx'
    torch.onnx.export(model, (torch.randn(1, N_MELS, 256),), str(path), opset_version=17,
        dynamo=False, input_names=['mel'], output_names=['salience'],
        dynamic_axes={'mel': {0: 'B', 2: 'T'}, 'salience': {0: 'B', 1: 'T'}})
    frontend = MelSpectrogram(N_MELS, SAMPLE_RATE, WINDOW_LENGTH, 160, None, MEL_FMIN, MEL_FMAX)
    np.savez_compressed(args.output / 'frontend.npz', mel=frontend.mel_basis.numpy(),
                        hann=torch.hann_window(WINDOW_LENGTH).numpy())
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 6
    session = ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
    parity = []
    with torch.inference_mode():
        for count in (128, 256, 512):
            mel = torch.randn(1, N_MELS, count)
            expected = model(mel).numpy()
            actual = session.run(None, {'mel': mel.numpy()})[0]
            error = float(np.max(abs(actual - expected)))
            if error > 1e-4:
                raise AssertionError('Pitch observer export changed output')
            parity.append({'frames': count, 'max_absolute_error': error})
    manifest = {'sample_rate': SAMPLE_RATE, 'fft_size': WINDOW_LENGTH, 'hop_size': 160,
        'pitch_bins': 360, 'cents_origin': 1997.3794084376191, 'cents_step': 20.,
        'checkpoint_sha256': hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        'onnx_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'frontend_sha256': hashlib.sha256((args.output / 'frontend.npz').read_bytes()).hexdigest(),
        'parity': parity, 'source': 'Original released RMVPE E2E0 weights, no retraining'}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    print(json.dumps(parity), flush=True)


if __name__ == '__main__':
    main()
