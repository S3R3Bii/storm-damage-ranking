import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ingest import cents,quantile_cents
from accounting import scenario_values,units,summarize
import numpy as np


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


class AccountingBoundaries(unittest.TestCase):
    def setUp(self):
        self.cal={'type_thresholds':{'Hail':{'median_cents':100,'p90_cents':1000}},'pooled_p99_cap_cents':500}

    def test_blank_zero_and_cap(self):
        self.assertEqual(scenario_values(None,'Hail',self.cal),[0,100,1000,0,100,500])
        self.assertEqual(scenario_values(0,'Hail',self.cal),[0]*6)
        self.assertEqual(scenario_values(10000,'Hail',self.cal),[10000]*3+[500]*3)

    def test_equal_year_weights_and_exact_ties(self):
        a=np.zeros((6,6),dtype=np.int64);b=a.copy();a[:,0]=10;b[:,1]=1000
        score,rank,ties=summarize([a,b])
        self.assertEqual(list(score[0,:2]),[.5,.5])
        self.assertEqual(list(rank[0,:2]),[1,2])
        self.assertTrue(np.all(ties==1))
        self.assertNotEqual(float(score[0,0]),10/1010)

    def test_episode_preserves_two_state_vector(self):
        reports=[dict(source_row=1,event_id=1,episode_id=10,state='ILLINOIS',event_type='Hail',damage_cents='10'),
                 dict(source_row=2,event_id=2,episode_id=10,state='INDIANA',event_type='Hail',damage_cents='20'),
                 dict(source_row=3,event_id=3,episode_id=20,state='OHIO',event_type='Hail',damage_cents='30')]
        ids,cluster=units(reports,self.cal,'episode');_,event=units(reports,self.cal,'event')
        self.assertEqual(ids,[10,20]);self.assertTrue(np.array_equal(cluster.sum(axis=0),event.sum(axis=0)))
        sampled=np.array([2,0])@cluster
        self.assertEqual(list(sampled.reshape(6,6)[0]),[20,40,0,0,0,0])

    def test_undefined_stratum_and_invalid_unit(self):
        with self.assertRaises(ValueError):summarize([np.zeros((6,6),dtype=np.int64)])
        with self.assertRaises(ValueError):summarize([])
        with self.assertRaises(ValueError):units([],self.cal,'other')


if __name__=='__main__':unittest.main()
