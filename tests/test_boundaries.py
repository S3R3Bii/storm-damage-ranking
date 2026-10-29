import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ingest import cents,quantile_cents


class SourceBoundaries(unittest.TestCase):
    def test_damage_units_and_zero(self):
        for token,expected in [('10.00K',1000000),('2M',200000000),('1.5B',150000000000),('0.00K',0),('12.34',1234),('0',0),(' 5k ',500000)]:
            with self.subTest(token=token):self.assertEqual(cents(token),expected)
        self.assertIsNone(cents(''));self.assertIsNone(cents('  '))

    def test_invalid_tokens(self):
        for token in ['-1K','NaN','inf','3Q','1e3','1.2.3M','0.001']:
            with self.subTest(token=token),self.assertRaises(ValueError):cents(token)

    def test_type7_interpolation(self):
        self.assertEqual(quantile_cents([0,10,20],.9),18)
        self.assertEqual(quantile_cents([1,2],.5),2)
        self.assertEqual(quantile_cents([0,1],.5),0)
        self.assertEqual(quantile_cents([5],.99),5)

    def test_invalid_quantiles(self):
        for values,p in [([], .5),([1],-1),([1],2)]:
            with self.assertRaises(ValueError):quantile_cents(values,p)


if __name__=='__main__':unittest.main()
