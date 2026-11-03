"""Independent diagnostic score sequences, deliberately outside inference.

Counts pitch substitutions, missing attacks and extra attacks separately.
Outer phrase spans are approximate: this does NOT measure rhythm accuracy,
whole-song accuracy, subjective quality or whether a performance follows a
printed score exactly. Never use these targets as decoder inputs.
"""
from pathlib import Path
import csv
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/vocal_transcription_v9_20261029'


def align(expected, observed):
    cells = {(0, 0): (0, [])}
    for i in range(len(expected) + 1):
        for j in range(len(observed) + 1):
            if i == j == 0:
                continue
            options = []
            if i and j:
                cost, path = cells[i - 1, j - 1]
                operation = 'match' if expected[i - 1] == observed[j - 1] else 'pitch_substitution'
                options.append((cost + (operation != 'match'), path + [operation]))
            if i:
                cost, path = cells[i - 1, j]
                options.append((cost + 1, path + ['missing_attack']))
            if j:
                cost, path = cells[i, j - 1]
                options.append((cost + 1, path + ['extra_attack']))
            cells[i, j] = min(options, key=lambda q: q[0])
    cost, path = cells[len(expected), len(observed)]
    return {'edit_distance': cost, **{key: path.count(key) for key in
            ('match', 'pitch_substitution', 'missing_attack', 'extra_attack')}}


def main():
    fixture = json.loads((BASE / 'score_phrase_checks_v2.json').read_text(encoding='utf8'))
    rows = []
    for recording in ('zuguo', 'qiansixi'):
        paths = list((BASE / 'legacy_ablation' / recording).glob('*.csv'))
        paths += list((BASE / 'fixed_contexts' / recording).glob('*.csv'))
        paths += list((BASE / 'hybrid' / recording).glob('notes.csv'))
        for path in paths:
            data = list(csv.DictReader(path.open(encoding='utf8')))
            for check in fixture['checks']:
                if check['recording'] != recording:
                    continue
                a, z = check['source_span_s']
                observed = [int(n['midi']) for n in data if a <= int(n['start_ms']) / 1000 < z]
                rows.append({'recording': recording, 'variant': path.stem, 'text': check['text'],
                    'expected': check['pitches'], 'observed': observed,
                    **align(check['pitches'], observed), 'source': str(path.relative_to(ROOT)),
                    'rhythm_accuracy_measured': False, 'real_world_90_percent_verified': False})
    (BASE / 'phrase_refinement_results.json').write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf8')
    totals = {}
    for row in rows:
        key = row['recording'] + '/' + row['variant']
        target = totals.setdefault(key, {k: 0 for k in ('match', 'pitch_substitution', 'missing_attack', 'extra_attack')})
        for k in target:
            target[k] += row[k]
    print(json.dumps(totals, indent=2))


if __name__ == '__main__':
    main()
