"""Validate fixed patient sources and preserve observed values without imputation."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

COLUMNS = ('HR', 'Temp', 'SBP', 'DBP', 'MAP', 'Resp', 'O2Sat', 'WBC',
           'Lactate', 'Creatinine', 'Bilirubin_total', 'Platelets', 'FiO2',
           'BUN', 'Glucose', 'pH')
# Conservative domain validation, not learned clinical clipping thresholds.
BOUNDS = {'O2Sat': (0, 100), 'FiO2': (0.21, 1), 'pH': (0, 14)}


def clean_value(column, text):
    value = float(text)
    if math.isnan(value):
        return '', 0, 0
    if not math.isfinite(value):
        return '', 1, 1
    low, high = BOUNDS.get(column, (0, math.inf))
    if value < low or value > high:
        return '', 1, 1
    return value, 1, 0


def preprocess(raw, splits, output):
    manifest = json.loads((splits / 'manifest.json').read_text())
    inventory = splits / 'patients.csv'
    if hashlib.sha256(inventory.read_bytes()).hexdigest() != manifest['patients_csv_sha256']:
        raise ValueError('Patient inventory hash mismatch')
    with inventory.open(newline='') as stream:
        patients = list(csv.DictReader(stream))
    if len(patients) != manifest['patient_count'] or len({p['patient_key'] for p in patients}) != len(patients):
        raise ValueError('Invalid patient inventory')
    for split in ('train', 'validation', 'test'):
        saved = (splits / f'{split}_ids.txt').read_text().splitlines()
        expected = {p['patient_key'] for p in patients if p['split'] == split}
        if len(saved) != len(set(saved)) or set(saved) != expected:
            raise ValueError(f'Invalid fixed split: {split}')
    output.mkdir(parents=True, exist_ok=False)
    fields = ['patient_key', 'patient_id', 'hospital_set', 'split', 'ICULOS', 'SepsisLabel']
    fields += list(COLUMNS)
    fields += [f'{c}_observed' for c in COLUMNS] + [f'{c}_invalid' for c in COLUMNS]
    quality = {h: {c: Counter() for c in COLUMNS} for h in 'AB'}
    counts = Counter()
    stats = {h: {c: {'min': None, 'max': None} for c in COLUMNS} for h in 'AB'}
    try:
        with ExitStack() as stack:
            writers = {}
            for split in ('train', 'validation', 'test'):
                stream = stack.enter_context(gzip.open(output / f'{split}.csv.gz', 'wt', newline=''))
                writers[split] = csv.DictWriter(stream, fieldnames=fields)
                writers[split].writeheader()
            for patient in patients:
                path = raw / patient['source_file']
                if hashlib.sha256(path.read_bytes()).hexdigest() != patient['sha256']:
                    raise ValueError(f'Source changed: {path}')
                records = []
                with path.open(newline='') as stream:
                    reader = csv.DictReader(stream, delimiter='|')
                    header = reader.fieldnames or []
                    if len(header) != len(set(header)) or not set(COLUMNS + ('ICULOS', 'SepsisLabel')).issubset(header):
                        raise ValueError(f'Invalid schema: {path}')
                    for row in reader:
                        if None in row or any(v is None for v in row.values()):
                            raise ValueError(f'Malformed row: {path}')
                        t = float(row['ICULOS'])
                        if not math.isfinite(t) or t < 1 or not t.is_integer() or row['SepsisLabel'] not in ('0', '1'):
                            raise ValueError(f'Invalid time/label: {path}')
                        records.append((int(t), row))
                if [t for t, _ in records] != sorted(t for t, _ in records):
                    counts['reordered_patients'] += 1
                records.sort(key=lambda item: item[0])
                times = [t for t, _ in records]
                if any(b != a + 1 for a, b in zip(times, times[1:])):
                    raise ValueError(f'Duplicate or missing time: {path}')
                if len(records) != int(patient['hours']) or sum(int(r['SepsisLabel']) for _, r in records) != int(patient['positive_hours']):
                    raise ValueError(f'Inventory count mismatch: {path}')
                for t, row in records:
                    result = {k: patient[k] for k in ('patient_key', 'patient_id', 'hospital_set', 'split')}
                    result.update(ICULOS=t, SepsisLabel=row['SepsisLabel'])
                    for column in COLUMNS:
                        value, observed, invalid = clean_value(column, row[column])
                        result[column] = value
                        result[f'{column}_observed'] = observed
                        result[f'{column}_invalid'] = invalid
                        q = quality[patient['hospital_set']][column]
                        q['raw_missing'] += 1 - observed
                        q['invalid'] += invalid
                        q['valid'] += observed - invalid
                        if value != '':
                            s = stats[patient['hospital_set']][column]
                            s['min'] = value if s['min'] is None else min(value, s['min'])
                            s['max'] = value if s['max'] is None else max(value, s['max'])
                    writers[patient['split']].writerow(result)
                    counts['rows'] += 1
                counts['patients'] += 1
        report = {'status': 'complete', 'patients_csv_sha256': manifest['patients_csv_sha256'],
                  'counts': dict(counts), 'columns': COLUMNS, 'bounds': BOUNDS,
                  'rules': 'No imputation/scaling/clipping; nonfinite, negative and explicit domain violations become missing; raw observed and invalid flags retained; FiO2 is a fraction, no guessed percent conversion',
                  'quality_by_hospital': quality, 'valid_ranges_by_hospital': stats}
        (output / 'quality_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps({'counts': dict(counts), 'invalid_by_hospital': {h: {c: q['invalid'] for c, q in quality[h].items()} for h in 'AB'}}, indent=2))
    except Exception as error:
        (output / 'FAILED.txt').write_text(str(error) + '\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=Path('physionet-data/physionet.org/files/challenge-2019/1.0.0/training'))
    parser.add_argument('--splits', type=Path, default=Path('data/interim/patient_splits_v1'))
    parser.add_argument('--output', type=Path, default=Path('data/interim/preprocessed_v1'))
    args = parser.parse_args()
    preprocess(args.raw, args.splits, args.output)
