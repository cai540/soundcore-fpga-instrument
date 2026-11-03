"""Native GAME observations, retaining uncertainty instead of editing notes.

Original weights stay immutable. Exposing two existing graph tensors changes
the API only; it adds no trained parameters or song-dependent information.
The cache contains model observations, never hand-edited melody answers.
"""
from pathlib import Path
import hashlib
import json
import os
import tempfile
import numpy as np
from .types import EncodedAudio, ModelObservation


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_npz(path, **arrays):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.npz', delete=False) as stream:
        temporary = Path(stream.name)
        np.savez_compressed(stream, **arrays)
    os.replace(temporary, path)


class GameModel:
    def __init__(self, model_directory, cache_directory, threads=6, language='zh', steps=8):
        import onnxruntime as ort
        directory = Path(model_directory)
        configs = list(directory.rglob('config.json'))
        if len(configs) != 1:
            raise ValueError('Exactly one unpacked GAME config is required')
        self.directory = configs[0].parent
        self.config = json.loads(configs[0].read_text(encoding='utf8'))
        self.cache = Path(cache_directory)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.rate = int(self.config['samplerate'])
        self.dt = float(self.config['timestep'])
        self.steps = int(steps)
        if self.steps <= 0 or language not in self.config.get('languages', {}):
            raise ValueError('Positive step count and a supported language required')
        self.language = int(self.config['languages'][language])
        self.fingerprints = {p.name: _sha(p) for p in self.directory.iterdir() if p.is_file()}
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        ort.set_seed(0)
        self.sessions = {}
        for name in ('encoder', 'segmenter', 'estimator', 'bd2dur'):
            path = self.directory / (name + '.onnx')
            if name in ('segmenter', 'estimator'):
                path = self._expose(path, name)
            self.sessions[name] = ort.InferenceSession(str(path), sess_options=options,
                                                     providers=['CPUExecutionProvider'])

    def _expose(self, path, role):
        signature = hashlib.sha256((_sha(path) + ':evidence-output-v1').encode()).hexdigest()
        destination = self.cache / 'graphs' / (signature + '.onnx')
        if destination.exists():
            return destination
        import onnx
        graph = onnx.load(str(path))
        if role == 'estimator':
            # Select the pitch probability feeding ArgMax, not unrelated
            # attention softmax tensors. Fail closed on an unknown graph.
            names = {n.input[0] for n in graph.graph.node if n.op_type == 'ArgMax'}
            nodes = [n for n in graph.graph.node if n.op_type == 'Sigmoid' and n.output[0] in names]
            if len(nodes) != 1:
                raise ValueError('Unsupported GAME pitch head')
            tensor, shape = nodes[0].output[0], ['B', 'N', None]
        else:
            nodes = [n for n in graph.graph.node if n.op_type == 'GreaterOrEqual' and 'threshold' in n.input]
            if len(nodes) != 1:
                raise ValueError('Unsupported GAME boundary head')
            tensor, shape = next(q for q in nodes[0].input if q != 'threshold'), ['B', 'T']
        graph.graph.output.append(onnx.helper.make_tensor_value_info(tensor, onnx.TensorProto.FLOAT, shape))
        onnx.checker.check_model(graph)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.onnx', delete=False) as stream:
            temporary = Path(stream.name)
        onnx.save(graph, str(temporary))
        os.replace(temporary, destination)
        return destination

    def encode(self, waveform):
        waveform = np.asarray(waveform, dtype=np.float32)
        if waveform.ndim != 1 or len(waveform) < self.rate / 10 or not np.isfinite(waveform).all():
            raise ValueError('Finite mono native-rate PCM, at least 0.1 seconds, required')
        digest = hashlib.sha256(waveform.tobytes()).hexdigest()
        key = hashlib.sha256(json.dumps([digest, self.rate, self.fingerprints['encoder.onnx']]).encode()).hexdigest()
        path = self.cache / 'encoder' / (key + '.npz')
        if path.exists():
            with np.load(path, allow_pickle=False) as q:
                xs, xe, mask = q['segmentation'], q['estimation'], q['mask']
        else:
            xs, xe, mask = self.sessions['encoder'].run(None, {
                'waveform': waveform[None, :], 'duration': np.array([len(waveform) / self.rate], np.float32)})
            _write_npz(path, segmentation=xs, estimation=xe, mask=mask)
        return EncodedAudio(xs, xe, mask, len(waveform), self.rate, digest)

    def segment(self, encoded, known_frames=()):
        mask = encoded.mask
        known = np.zeros(mask.shape, bool)
        for frame in known_frames:
            if not 0 < frame < encoded.frames:
                raise ValueError('Conditioned boundary outside the audio grid')
            known[0, frame] = True
        boundaries = known.copy()
        probability = np.zeros(mask.shape, np.float32)
        feeds = {'x_seg': encoded.segmentation, 'known_boundaries': known, 'maskT': mask,
                 'threshold': np.array(.2, np.float32), 'radius': np.array(2, np.int64),
                 'language': np.array([self.language], np.int64)}
        for t in np.arange(self.steps, dtype=np.float32) / self.steps:
            feeds.update(prev_boundaries=boundaries, t=np.array([t], np.float32))
            boundaries, probability = self.sessions['segmenter'].run(None, feeds)
        cuts = np.r_[0, np.flatnonzero(boundaries[0, :encoded.frames]), encoded.frames]
        cuts = np.unique(cuts).astype(int)
        activation = self.estimate(encoded, cuts)
        return ModelObservation(cuts, probability[0, :encoded.frames].clip(0, 1), activation)

    def estimate(self, encoded, cuts):
        cuts = np.asarray(cuts, int)
        if (len(cuts) < 2 or cuts[0] != 0 or cuts[-1] != encoded.frames
                or np.any(np.diff(cuts) <= 0)):
            raise ValueError('An ordered, complete source-time partition is required')
        key = hashlib.sha256(json.dumps([encoded.source_sha256, self.fingerprints, cuts.tolist(),
                                       'pitch-activation-v1'], sort_keys=True).encode()).hexdigest()
        path = self.cache / 'pitch' / (key + '.npz')
        if path.exists():
            with np.load(path, allow_pickle=False) as q:
                return q['activation']
        boundaries = np.zeros(encoded.mask.shape, bool)
        boundaries[0, cuts[1:-1]] = True
        _, note_mask = self.sessions['bd2dur'].run(None, {'boundaries': boundaries, 'maskT': encoded.mask})
        _, _, activation = self.sessions['estimator'].run(None, {
            'x_est': encoded.estimation, 'boundaries': boundaries, 'maskT': encoded.mask,
            'maskN': note_mask, 'threshold': np.array(.2, np.float32)})
        activation = activation[0, :len(cuts) - 1]
        if activation.shape != (len(cuts) - 1, 257):
            raise ValueError('Expected the released GAME 0..128 half-semitone pitch grid')
        _write_npz(path, activation=activation)
        return activation
