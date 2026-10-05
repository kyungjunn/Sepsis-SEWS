"""Build patient-level 70/15/15 splits without third-party dependencies."""
import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

SPLITS = ("train", "validation", "test")
RATIOS = (0.70, 0.15, 0.15)


def scan_patients(root):
    patients = []
    for hospital in ("A", "B"):
        files = sorted((root / f"training_set{hospital}").glob("*.psv"))
        if not files:
            raise ValueError(f"No patient files for hospital {hospital}")
        for path in files:
            count = positives = 0
            previous_time = None
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with path.open(newline="") as stream:
                reader = csv.DictReader(stream, delimiter="|")
                if not {"SepsisLabel", "ICULOS"}.issubset(reader.fieldnames or []):
                    raise ValueError(f"Missing required columns: {path}")
                for row in reader:
                    label = row["SepsisLabel"]
                    time = float(row["ICULOS"])
                    if label not in ("0", "1"):
                        raise ValueError(f"Invalid label: {path}")
                    if not time.is_integer() or time < 1 or (previous_time is not None and time != previous_time + 1):
                        raise ValueError(f"Invalid hourly time axis: {path}")
                    previous_time = time
                    count += 1
                    positives += int(label)
            if count == 0:
                raise ValueError(f"Empty patient file: {path}")
            patients.append({"patient_key": f"{hospital}:{path.stem}", "patient_id": path.stem,
                             "hospital_set": hospital, "hours": count,
                             "positive_hours": positives, "septic": int(positives > 0),
                             "source_file": str(path.relative_to(root)), "sha256": digest})
    return patients


def assign_splits(patients, seed=42):
    keys = [p["patient_key"] for p in patients]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate patient keys")
    groups = defaultdict(list)
    for patient in patients:
        groups[(patient["hospital_set"], patient["septic"])].append(dict(patient))
    result = []
    for group, members in sorted(groups.items()):
        members.sort(key=lambda p: p["patient_key"])
        random.Random(f"{seed}:{group[0]}:{group[1]}").shuffle(members)
        exact = [len(members) * ratio for ratio in RATIOS]
        counts = [int(value) for value in exact]
        order = sorted(range(3), key=lambda i: (-(exact[i] - counts[i]), i))
        for i in order[:len(members) - sum(counts)]:
            counts[i] += 1
        start = 0
        for split, count in zip(SPLITS, counts):
            for patient in members[start:start + count]:
                patient["split"] = split
                result.append(patient)
            start += count
    return sorted(result, key=lambda p: p["patient_key"])


def build(root, output, seed):
    patients = assign_splits(scan_patients(root), seed)
    output.mkdir(parents=True, exist_ok=True)
    targets = [output / "patients.csv", output / "manifest.json"] + [output / f"{s}_ids.txt" for s in SPLITS]
    if any(p.exists() for p in targets):
        raise FileExistsError("Split artifacts already exist; use a new output directory to preserve fixed splits")
    with targets[0].open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(patients[0]))
        writer.writeheader()
        writer.writerows(patients)
    summary = {}
    for split in SPLITS:
        subset = [p for p in patients if p["split"] == split]
        (output / f"{split}_ids.txt").write_text("".join(p["patient_key"] + "\n" for p in subset))
        summary[split] = {hospital: {"patients": len(items), "septic_patients": sum(p["septic"] for p in items),
                                    "hours": sum(p["hours"] for p in items),
                                    "positive_hours": sum(p["positive_hours"] for p in items)}
                          for hospital in ("A", "B")
                          for items in [[p for p in subset if p["hospital_set"] == hospital]]}
    manifest = {"seed": seed, "ratios": dict(zip(SPLITS, RATIOS)),
                "algorithm": "sorted hospital/septic strata; Python Random string seed; largest remainder rounding",
                "source_root": str(root.resolve()), "patient_count": len(patients),
                "patients_csv_sha256": hashlib.sha256(targets[0].read_bytes()).hexdigest(),
                "summary": summary}
    targets[1].write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("physionet-data/physionet.org/files/challenge-2019/1.0.0/training"))
    parser.add_argument("--output", type=Path, default=Path("data/interim/patient_splits_v1"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    build(args.raw, args.output, args.seed)
