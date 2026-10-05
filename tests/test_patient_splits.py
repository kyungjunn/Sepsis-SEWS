import unittest
from collections import Counter
from scripts.build_patient_splits import assign_splits


class PatientSplitTests(unittest.TestCase):
    def setUp(self):
        self.patients = [{"patient_key": f"{h}:{s}:{i}", "hospital_set": h, "septic": s}
                         for h in ("A", "B") for s in (0, 1) for i in range(100)]

    def test_stratification_and_disjointness(self):
        result = assign_splits(self.patients)
        self.assertEqual(len({p["patient_key"] for p in result}), 400)
        counts = Counter((p["hospital_set"], p["septic"], p["split"]) for p in result)
        for h in ("A", "B"):
            for s in (0, 1):
                for split, n in (("train", 70), ("validation", 15), ("test", 15)):
                    self.assertEqual(counts[h, s, split], n)

    def test_reproducible_independent_of_input_order(self):
        self.assertEqual(assign_splits(self.patients), assign_splits(list(reversed(self.patients))))
        self.assertNotEqual(assign_splits(self.patients, 42), assign_splits(self.patients, 43))

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            assign_splits(self.patients + [self.patients[0]])

    def test_rounding_preserves_all_patients(self):
        for n in range(1, 20):
            result = assign_splits(self.patients[:n])
            self.assertEqual(len(result), n)
            self.assertEqual(len({p["patient_key"] for p in result}), n)


if __name__ == "__main__":
    unittest.main()
