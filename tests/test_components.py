'''
Module with functions to test functions in components.py
'''
import ROOT
import zfit
import pytest

from rx_data.rdf_getter import RDFGetter
from rx_fitter          import components as cmp

# --------------------------------------------------------------
@pytest.fixture(scope='session', autouse=True)
def _intiailize():
    RDFGetter.samples = {
        'main'       : '/home/acampove/external_ssd/Data/samples/main.yaml',
        'mva'        : '/home/acampove/external_ssd/Data/samples/mva.yaml',
        'hop'        : '/home/acampove/external_ssd/Data/samples/hop.yaml',
        'cascade'    : '/home/acampove/external_ssd/Data/samples/cascade.yaml',
        'jpsi_misid' : '/home/acampove/external_ssd/Data/samples/jpsi_misid.yaml'}
# --------------------------------------------------------------
def test_mc():
    '''
    Testing creation of PDF from MC sample
    '''
    obs=zfit.Space('B_const_mass_M', limits=(4500, 6000))
    trigger = 'Hlt2RD_BuToKpEE_MVA'

    cmp_sig = cmp.get_mc(obs = obs, sample = 'Bu_JpsiK_ee_eq_DPC' , trigger = trigger, q2bin='jpsi', model=['cbl', 'cbl', 'cbr'])
    cmp_sig.run()
# --------------------------------------------------------------
