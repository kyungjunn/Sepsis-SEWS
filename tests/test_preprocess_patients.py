import unittest
from scripts.preprocess_patients import clean_value


class CleanValueTests(unittest.TestCase):
    def test_missing_is_not_observed(self):
        self.assertEqual(clean_value('HR', 'NaN'), ('', 0, 0))

    def test_invalid_retains_observation_flag(self):
        for c, v in [('HR', '-1'), ('O2Sat', '101'), ('FiO2', '2'), ('pH', '15'), ('HR', 'inf')]:
            self.assertEqual(clean_value(c, v), ('', 1, 1))

    def test_domain_boundaries(self):
        for c, v in [('FiO2', '0.21'), ('FiO2', '1'), ('O2Sat', '100'), ('pH', '7.4')]:
            self.assertEqual(clean_value(c, v), (float(v), 1, 0))

    def test_extreme_not_arbitrarily_clipped(self):
        self.assertEqual(clean_value('Lactate', '50'), (50.0, 1, 0))

    def test_malformed_number_rejected(self):
        with self.assertRaises(ValueError):
            clean_value('HR', 'broken')


if __name__ == '__main__':
    unittest.main()
