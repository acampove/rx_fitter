'''
Module with Reader class used to read weights to normalize between inclusive samples
'''

import os
import glob
from importlib.resources import files

import pandas    as pnd
from dmu.logging.log_store import LogStore
from rx_fitter             import pdg_utils as pu

log = LogStore.add_logger('rx_fitter:inclusive_sample_weights')
#---------------------------
class Reader:
    '''
    Class used to add weights that normalize inclusive samples
    '''
    #---------------------------
    def __init__(self, df : pnd.DataFrame):
        self._df   = df
        self._fu   = 0.408
        self._fs   = 0.100

        self._d_fev       = {}
        self._d_tp_st     = None
        self._initialized = False
    #---------------------------
    def _initialize(self):
        if self._initialized:
            return

        self._cache_stats()

        self._initialized = True
    #---------------------------
    def _get_br_wgt(self, proc : str) -> float:
        '''
        Will return ratio: 

        decay file br / pdg_br 
        '''
        #--------------------------------------------
        #Decay B+sig
        #0.1596  MyJ/psi    K+           SVS ;
        #--------------------------------------------
        #Decay B0sig
        #0.1920  MyJ/psi    MyK*0        SVV_HELAMP PKHplus PKphHplus PKHzero PKphHzero PKHminus PKphHminus ;
        #--------------------------------------------
        #Decay B_s0sig
        #0.1077  MyJ/psi    Myphi        PVV_CPLH 0.02 1 Hp pHp Hz pHz Hm pHm;
        #--------------------------------------------
        if proc == 'bp':
            return pu.get_bf('B+ --> J/psi(1S) K+') / 0.1596

        if proc == 'bd':
            return pu.get_bf('B0 --> J/psi(1S) K0') / 0.1920

        if proc == 'bs':
            return pu.get_bf('B_s()0 --> J/psi(1S) phi') / 0.1077

        raise ValueError(f'Invalid process {proc}')
    #---------------------------
    def _get_hd_wgt(self, proc : str) -> float:
        '''
        Will return hadronization fractions used as weights
        '''
        if proc in ['bp', 'bd']:
            return self._fu

        if proc == 'bs':
            return self._fs

        raise ValueError(f'Invalid process: {row.proc}')
    #---------------------------
    def _get_stats(self, path):
        proc = os.path.basename(path).replace('.json', '')
        df   = pnd.read_json(path)

        return proc, df
    #---------------------------
    def _cache_stats(self):
        if self._d_tp_st is not None:
            return

        stats_wc = files('tools_data').joinpath('inclusive_mc_stats/*.json')
        stats_wc = str(stats_wc)
        l_stats  = glob.glob(stats_wc)
        if len(l_stats) == 0:
            raise ValueError(f'No file found in: {stats_wc}')

        l_tp_st = [ self._get_stats(path) for path in l_stats ]
        self._d_tp_st = dict(l_tp_st)
    #---------------------------
    def _good_rows(self, r1 : pnd.Series, r2 : pnd.Series) -> bool:
        if {r1.Polarity, r2.Polarity} != {'MagUp', 'MagDown'}:
            log.error('Latest rows are not of opposite polarities')
            return False

        if r1.Events <= 0 or r2.Events <= 0:
            log.error('Either polarity number of events is negative')
            return False

        return True
    #---------------------------
    def _get_st_wgt(self, proc : str) -> float:
        wgt = 1.
        log.warning('Assuming that all inclusive samples have same statistics')

        return wgt
    #---------------------------
    def _get_weight(self, row : pnd.Series) -> float:
        w1 = self._get_st_wgt(row.proc)
        w2 = self._get_hd_wgt(row.proc)
        w3 = self._get_br_wgt(row.proc)

        return w1 * w2 * w3
    #---------------------------
    def get_weights(self) -> pnd.Series:
        '''
        Returns:

        Pandas series with sample weights
        '''
        self._initialize()

        sr_wgt = self._df.apply(self._get_weight, axis=1)

        return sr_wgt
#---------------------------
