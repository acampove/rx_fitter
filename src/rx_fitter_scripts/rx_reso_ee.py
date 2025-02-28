'''
Script used to fit the resonant mode in the electron channel
'''
import json
import argparse

import ROOT
import zfit
from dmu.logging.log_store                   import LogStore
from rx_calibration.hltcalibration.dt_fitter import DTFitter
from rx_data.rdf_getter                      import RDFGetter
from rx_fitter                               import components as cmp

log = LogStore.add_logger('rx_fitter:rx_reso_ee')
# ------------------------------
class Data:
    '''
    Data class
    '''
    nbrem : int
    mass  : str
    kind  : str
    cpath : str

    dtf_tail = 5150

    cfg   = {
            'error_method' : 'minuit_hesse',
            'out_dir'      : 'plots/fit/data',
            'plotting'     :
            {
                'nbins'   : 30,
                'stacked' : True,
                'd_leg'   : {
                    'Bu_JpsiK_ee_eq_DPC' : r'$B^+\to K^+J/\psi(\to e^+e^-)$',
                    'Bu_JpsiPi_ee_eq_DPC': r'$B^+\to \pi^+J/\psi(\to e^+e^-)$',
                    'combinatorial'      : 'Combinatorial',
                    }
                },
            }

    RDFGetter.samples = {
        'main'       : '/home/acampove/external_ssd/Data/samples/main.yaml',
        'mva'        : '/home/acampove/external_ssd/Data/samples/mva.yaml',
        'hop'        : '/home/acampove/external_ssd/Data/samples/hop.yaml',
        'cascade'    : '/home/acampove/external_ssd/Data/samples/cascade.yaml',
        'jpsi_misid' : '/home/acampove/external_ssd/Data/samples/jpsi_misid.yaml'}
# ------------------------------
def _get_constraints() -> dict[str,str]:
    if Data.cpath is None:
        return

    with open(Data.cpath, encoding='utf-8') as ifile:
        d_const = json.load(ifile)

    d_const_yield = { name : value for name, value in d_const.items() if name.startswith('n') }

    return d_const_yield
# ------------------------------
def _get_limits() -> tuple[int,int]:
    if Data.kind == 'bcn':
        return 5050, 5600

    if Data.kind == 'wide':
        return 4500, 5600

    if Data.kind == 'largest':
        return 4500, 6000

    if Data.kind == 'no_dtf_tail' and Data.mass == 'B_const_mass_M':
        return Data.dtf_tail, 5600

    if Data.kind == 'no_dtf_tail' and Data.mass == 'B_M':
        return 4500, 6000

    raise ValueError(f'Invalid kind: {Data.kind}')
# ------------------------------
def _get_cuts() -> dict[str,str]:
    d_cut = {}
    d_cut['nbrem'] = f'nbrem == {Data.nbrem}' if Data.nbrem in [0, 1] else f'nbrem >= {Data.nbrem}'

    if Data.kind == 'no_dtf_tail':
        d_cut[Data.kind] = f'B_const_mass_M > {Data.dtf_tail}'

    return d_cut
# ------------------------------
def _parse_args() -> None:
    parser = argparse.ArgumentParser(description='Script used to fit resonant electron mode')
    parser.add_argument('-b', '--nbrem' , type=int, help='Brem category'   , required=True, choices=[0,1,2])
    parser.add_argument('-m', '--mass'  , type=str, help='Branch with mass', required=True, choices=['B_M', 'B_const_mass_M'])
    parser.add_argument('-k', '--kind'  , type=str, help='Type of fit'     , required=True, choices=['bcn', 'wide', 'largest', 'no_dtf_tail'])
    parser.add_argument('-c', '--cpath' , type=str, help='Path to JSON file with parameters to constraint')
    args = parser.parse_args()

    Data.nbrem = args.nbrem
    Data.mass  = args.mass
    Data.kind  = args.kind
    Data.cpath = args.cpath
# ------------------------------
def main():
    '''
    Start here
    '''
    _parse_args()

    trigger = 'Hlt2RD_BuToKpEE_MVA'
    q2bin   = 'jpsi'
    d_cut   = _get_cuts()
    t_lim   = _get_limits()

    obs     = zfit.Space(Data.mass, limits=t_lim)

    cmp_sig = cmp.get_mc(obs = obs, sample = 'Bu_JpsiK_ee_eq_DPC' , trigger=trigger, q2bin=q2bin, nbrem=Data.nbrem)
    cmp_csp = cmp.get_mc(obs = obs, sample = 'Bu_JpsiPi_ee_eq_DPC', trigger=trigger, q2bin=q2bin, nbrem=Data.nbrem)
    cmp_prc = cmp.get_prc(obs= obs, trigger=trigger, q2bin=q2bin, name='no_tail', cuts = d_cut, bw = 20)
    cmp_cmb = cmp.get_cb(obs = obs, kind='exp')

    rdf = cmp.get_rdf(sample='DATA*', q2bin=q2bin, trigger=trigger, cuts = d_cut)

    out_dir = Data.cfg['out_dir']
    Data.cfg['out_dir']= f'{out_dir}/nbrem_{Data.nbrem:03}'

    d_const = _get_constraints()

    obj = DTFitter(rdf = rdf, components = [cmp_cmb, cmp_prc, cmp_csp, cmp_sig], cfg=Data.cfg)
    obj.fit(constraints = d_const)
# ------------------------------
if __name__ == '__main__':
    main()
