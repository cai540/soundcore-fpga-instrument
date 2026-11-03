"""Observation preparation and one decoder invocation per source phrase."""
from dataclasses import asdict, dataclass
from pathlib import Path
import csv
import hashlib
import numpy as np
from . import audio
from .decoder import candidate_cuts, decode, tonal_prior, interval_candidates
from .types import DecodeConfig, IntervalEvidence, ModelObservation, Note
from .pitch import interval_likelihood

EVIDENCE_POLICY = 'native-30-45s-fixed-log-pool-separate-voicing-v2'


@dataclass(frozen=True)
class PhraseEvidence:
    offset_ms: int
    observation: ModelObservation
    phonetic: np.ndarray
    intervals: tuple[IntervalEvidence, ...]


@dataclass(frozen=True)
class RecordingEvidence:
    duration_ms: int
    source_sha256: str
    phrases: tuple[PhraseEvidence, ...]
    observers: tuple[tuple[str, str], ...] = ()


class Transcriber:
    def __init__(self, model, config=DecodeConfig(), word_observer=None, pitch_observer=None):
        self.model = model
        self.config = config
        self.word_observer = word_observer
        self.pitch_observer = pitch_observer

    def prepare(self, recording, progress=lambda *args: None):
        if self.model is None or self.word_observer is None or self.pitch_observer is None:
            raise ValueError('Melody, word and pitch observers are required to prepare audio')
        recording = audio.resample(recording, self.model.rate)
        f0, confidence = self.pitch_observer.observe(recording.samples, recording.rate)
        phrases = []
        chunks = audio.phrase_chunks(recording, min_seconds=30., max_seconds=45.)
        hop = round(self.model.rate * self.model.dt)
        for index, chunk in enumerate(chunks):
            pcm = recording.samples[chunk.first_frame * hop:chunk.last_frame * hop]
            if len(pcm) < self.model.rate / 10:
                continue
            encoded = self.model.encode(pcm)
            observation = self.model.segment(encoded)
            local_f0 = f0[chunk.first_frame:chunk.last_frame]
            local_confidence = confidence[chunk.first_frame:chunk.last_frame]
            measured = self.word_observer.probability(pcm, self.model.rate, encoded.frames, local_f0)
            cuts = candidate_cuts(observation, measured)
            intervals = tuple(IntervalEvidence(v.start, v.end, v.activation,
                interval_likelihood(local_f0, local_confidence, v.start, v.end), v.voiced_probability)
                for v in interval_candidates(observation, cuts, self.config.max_boundary_span))
            phrases.append(PhraseEvidence(chunk.first_frame * 10, observation, measured, intervals))
            progress(index + 1, len(chunks))
        observers = tuple(sorted([('game:' + k, v) for k, v in self.model.fingerprints.items()]
            + [('word', self.word_observer.metadata['onnx_sha256']),
               ('word_frontend', self.word_observer.metadata['frontend_sha256']),
               ('pitch', self.pitch_observer.metadata['onnx_sha256']),
               ('pitch_frontend', self.pitch_observer.metadata['frontend_sha256'])]))
        return RecordingEvidence(recording.duration_ms,
            hashlib.sha256(recording.samples.tobytes()).hexdigest(), tuple(phrases), observers)

    def transcribe(self, evidence):
        prior, key_audit = tonal_prior([p.observation for p in evidence.phrases])
        durations = [d * .01 for p in evidence.phrases for d, activity in
                     zip(np.diff(p.observation.cuts), p.observation.pitch_activation) if activity.max() >= .2]
        typical_duration = float(np.median(durations)) if durations else .3
        result, audits = [], []
        for phrase in evidence.phrases:
            notes, audit = decode(phrase.observation, phrase.phonetic, phrase.intervals,
                                  self.config, prior, typical_duration)
            for note in notes:
                # This maps the measured model frame clock to the original
                # sample clock; it makes no pitch, articulation or merge edit.
                start = note.start_ms + phrase.offset_ms
                end = min(evidence.duration_ms, note.end_ms + phrase.offset_ms)
                if end > start:
                    result.append(Note(start, end, note.midi))
            audits.append({'offset_ms': phrase.offset_ms, **audit})
        if any(a.end_ms > b.start_ms for a, b in zip(result, result[1:])):
            raise RuntimeError('Phrase ownership produced overlapping notes')
        return result, {'config': asdict(self.config), 'tonality': key_audit, 'phrases': audits,
                        'recording_median_note_duration_s': typical_duration,
                        'postprocessing_corrections': 0}


def save_evidence(evidence, destination):
    """Portable observations for fast independent decoder/calibration tests."""
    arrays = {}
    for i, phrase in enumerate(evidence.phrases):
        has_f0 = [v.f0_likelihood is not None for v in phrase.intervals]
        if any(has_f0) and not all(has_f0):
            raise ValueError('A phrase must consistently provide acoustic pitch observations')
        prefix = str(i) + '_'
        arrays[prefix + 'offset'] = np.array(phrase.offset_ms)
        arrays[prefix + 'cuts'] = phrase.observation.cuts
        arrays[prefix + 'boundary'] = phrase.observation.boundary_probability
        arrays[prefix + 'raw_pitch'] = phrase.observation.pitch_activation
        arrays[prefix + 'phonetic'] = phrase.phonetic
        arrays[prefix + 'interval_bounds'] = np.array([(v.start, v.end) for v in phrase.intervals], int)
        arrays[prefix + 'interval_pitch'] = np.array([v.activation for v in phrase.intervals])
        arrays[prefix + 'interval_voiced'] = np.array([v.voiced_probability for v in phrase.intervals])
        if phrase.intervals and phrase.intervals[0].f0_likelihood is not None:
            arrays[prefix + 'interval_f0'] = np.array([v.f0_likelihood for v in phrase.intervals])
    arrays['duration_ms'] = np.array(evidence.duration_ms)
    arrays['phrase_count'] = np.array(len(evidence.phrases))
    arrays['source_sha256'] = np.array(evidence.source_sha256)
    arrays['policy'] = np.array(EVIDENCE_POLICY)
    arrays['observers'] = np.array(evidence.observers)
    np.savez_compressed(destination, **arrays)


def load_evidence(source):
    with np.load(source, allow_pickle=False) as q:
        if 'policy' not in q or str(q['policy']) != EVIDENCE_POLICY:
            raise ValueError('Incompatible experimental observations; prepare the audio with the current pipeline')
        phrases = []
        for i in range(int(q['phrase_count'])):
            prefix = str(i) + '_'
            obs = ModelObservation(q[prefix + 'cuts'], q[prefix + 'boundary'], q[prefix + 'raw_pitch'])
            bounds = q[prefix + 'interval_bounds']
            pitch = q[prefix + 'interval_pitch']
            voice = q[prefix + 'interval_voiced']
            f0 = q[prefix + 'interval_f0'] if prefix + 'interval_f0' in q else [None] * len(bounds)
            count = len(bounds)
            if (bounds.shape != (count, 2) or pitch.shape != (count, 257)
                    or voice.shape != (count,) or len(f0) != count):
                raise ValueError('Interval observation lengths or shapes do not match')
            intervals = tuple(IntervalEvidence(int(a), int(z), p, f, voice) for (a, z), p, f, voice in
                              zip(bounds, pitch, f0, voice))
            phrases.append(PhraseEvidence(int(q[prefix + 'offset']), obs, q[prefix + 'phonetic'], intervals))
        return RecordingEvidence(int(q['duration_ms']), str(q['source_sha256']), tuple(phrases),
                                 tuple(tuple(str(v) for v in pair) for pair in q['observers']))


def export(notes, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / 'notes.csv').open('w', encoding='utf8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['start_ms', 'duration_ms', 'midi'])
        for note in notes:
            writer.writerow([note.start_ms, note.end_ms - note.start_ms, note.midi])
    import mido
    midi = mido.MidiFile(ticks_per_beat=1000)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=500000))
    cursor = 0
    for note in notes:
        track.append(mido.Message('note_on', note=note.midi, velocity=80, time=(note.start_ms - cursor) * 2))
        track.append(mido.Message('note_off', note=note.midi, velocity=0, time=(note.end_ms - note.start_ms) * 2))
        cursor = note.end_ms
    midi.save(destination / 'source_clock.mid')
