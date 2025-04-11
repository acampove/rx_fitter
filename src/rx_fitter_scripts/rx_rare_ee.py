'''
Script used to fit the rare mode
'''
import os
import argparse
from importlib.resources import files

import yaml
import ROOT
import numpy
import zfit
import matplotlib.pyplot as plt
from ROOT                        import EnableImplicitMT
from zfit.core.data              import Data       as zdata
from zfit.core.basepdf           import BasePDF    as zpdf
from zfit.core.interfaces        import ZfitSpace  as zobs
from zfit.core.parameter         import Parameter  as zpar
from dmu.generic                 import hashing
from dmu.generic                 import utilities  as gut
from dmu.logging.log_store       import LogStore
from dmu.stats.zfit_plotter      import ZFitPlotter
from dmu.stats.fitter            import Fitter
from dmu.stats.utilities         import print_pdf
from rx_data.rdf_getter          import RDFGetter
from rx_selection                import selection  as sel
from rx_fitter                   import components as cmp
from rx_fitter.constraint_reader import ConstraintReader

log=LogStore.add_logger('rx_fitter:rx_rare_ee')
# --------------------------
class Data:
    '''
    Data class
    '''
    q2bin   : str

    cache_dir: str = '/tmp/rx_fitter/cache'
    mva_cut : str  = '(mva_cmb > 0.50) && (mva_prc > 0.85)'
    sample  : str  = 'DATA*'
    trigger : str  = 'Hlt2RD_BuToKpEE_MVA'
    version : str  = 'v1'
    mass    : str  = 'B_M_brem_track_2'
    minx    : int  = 4_500
    maxx    : int  = 6_100
    obs     : zobs = zfit.Space(mass, limits=(minx, maxx))
    nsig    : zpar = zfit.Parameter('nsig', 0, 0, 10_000)
    gut.TIMER_ON   = True

    log_level : int        = 20
    l_pdf     : list[zpdf] = []
# --------------------------------------------------------------
def _parse_args():
    parser = argparse.ArgumentParser(description='Script used to fit rare mode electron channel data for RK')
    parser.add_argument('-q', '--q2bin' , type=str, help='q2 bin', required=True, choices=['low', 'central', 'high'])
    parser.add_argument('-l', '--loglv' , type=int, help='Logging level', default=Data.log_level, choices=[10, 20, 30])
    args = parser.parse_args()

    Data.q2bin     = args.q2bin
    Data.log_level = args.loglv
# --------------------------------------------------------------
def _load_config(component : str) -> dict:
    cfg_path = files('rx_fitter_data').joinpath(f'rare_fit/{Data.version}/rk_ee/{component}.yaml')
    with open(cfg_path, encoding='utf-8') as ifile:
        cfg = yaml.safe_load(ifile)

    return cfg
# --------------------------
def _add_pdf_cmb() -> None:
    cfg  = _load_config(component = 'combinatorial')
    pdf  = cmp.get_cb(obs=Data.obs, q2bin=Data.q2bin, cfg=cfg)
    ncmb = zfit.Parameter('ncmb', 0, 0, 20_000)
    pdf  = pdf.create_extended(ncmb)

    Data.l_pdf.append(pdf)
# --------------------------
def _set_logs() -> None:
    LogStore.set_level('rx_fitter:constraint_reader', Data.log_level)
# --------------------------
def _add_pdf_prc(sample : str) -> None:
    cfg                   = _load_config(component='bxhsee')
    cfg['input']['q2bin'] = Data.q2bin
    cfg['selection']      = {'mva' : Data.mva_cut}

    pdf  = cmp.get_kde(obs=Data.obs, sample=sample, nbrem=None, cfg=cfg)
    scale= zfit.Parameter(f's{sample}', 0, 0, 10)
    nprc = zfit.ComposedParameter(f'n{sample}', lambda x : x['nsig'] * x['scale'], params={'nsig' : Data.nsig, 'scale' : scale})
    pdf.set_yield(nprc)

    Data.l_pdf.append(pdf)
# --------------------------
def _add_pdf_leak(sample : str) -> None:
    cfg                   = _load_config(component='ccbar_leak')
    cfg['input']['q2bin'] = Data.q2bin
    cfg['selection']      = {'mva' : Data.mva_cut}

    pdf   = cmp.get_kde(obs=Data.obs, sample=sample, nbrem=None, cfg=cfg)
    nleak = zfit.Parameter(f'n{sample}', 0, 0, 10_000)
    pdf.set_yield(nleak)

    Data.l_pdf.append(pdf)
# --------------------------
def _add_pdf_sig() -> None:
    cfg  = _load_config(component='signal')
    cfg['input']['q2bin'] = Data.q2bin

    pdf  = cmp.get_mc_reparametrized(obs=Data.obs, component_name='Signal', cfg=cfg, nbrem=None)
    pdf  = pdf.create_extended(Data.nsig)

    Data.l_pdf.append(pdf)
# --------------------------
@gut.timeit
def _get_pdf() -> zpdf:
    _add_pdf_cmb()
    _add_pdf_prc(sample='Bu_Kstee_Kpi0_eq_btosllball05_DPC')
    _add_pdf_prc(sample='Bd_Kstee_eq_btosllball05_DPC')

    if Data.q2bin == 'central':
        _add_pdf_leak(sample='Bu_JpsiK_ee_eq_DPC')

    if Data.q2bin == 'high':
        _add_pdf_prc(sample='Bs_phiee_eq_Ball_DPC')

    _add_pdf_sig()

    pdf = zfit.pdf.SumPDF(Data.l_pdf)

    return pdf
# --------------------------
@gut.timeit
def _get_data() -> zdata:
    gtr = RDFGetter(sample=Data.sample, trigger=Data.trigger)
    rdf = gtr.get_rdf()

    d_sel        = sel.selection(project='RK', trigger=Data.trigger, q2bin=Data.q2bin, process=Data.sample)
    d_sel['mva'] = Data.mva_cut

    hsh             = hashing.hash_object([d_sel, Data.sample, Data.trigger, Data.mass, Data.mva_cut])
    data_cache_path = f'{Data.cache_dir}/{hsh}.json'
    if os.path.isfile(data_cache_path):
        log.warning(f'Caching data from: {data_cache_path}')
        l_mass   = gut.load_json(data_cache_path)
        arr_mass = numpy.array(l_mass)
        data = zfit.Data.from_numpy(obs=Data.obs, array=arr_mass)

        #plt.hist(arr_mass, range=(4500, 6100), bins=50)
        #plt.show()

        return data

    for cut_name, cut_expr in d_sel.items():
        log.debug(f'{cut_name:<20}{cut_expr}')
        rdf = rdf.Filter(cut_expr, cut_name)

    arr_mass = rdf.AsNumpy([Data.mass])[Data.mass]
    log.info(f'Caching data to: {data_cache_path}')
    gut.dump_json(arr_mass.tolist(), data_cache_path)

    data = zfit.Data.from_numpy(obs=Data.obs, array=arr_mass)

    return data
# --------------------------
def _get_constraints(pdf : zpdf) -> dict[str,tuple[float,float]]:
    s_par  = pdf.get_params()
    l_name = [par.name for par in s_par]

    obj    = ConstraintReader(parameters = l_name, q2bin=Data.q2bin, mva_cut = Data.mva_cut)
    d_cns  = obj.get_constraints()

    return d_cns
# --------------------------
@gut.timeit
def _fit(pdf : zpdf, data : zdata, constraints : dict[str,tuple[float,float]]) -> None:
    cfg = {
            'constraints' : constraints,
            #'strategy'    : {'retry' : {'ntries' : 10, 'pvalue_thresh' : 0.05, 'ignore_status' : False}},
            }

    obj = Fitter(pdf, data)
    res = obj.fit(cfg=cfg)
    log.info(res)

    obj   = ZFitPlotter(data=data, model=pdf)
    obj.plot(nbins=50, stacked=True)
    plt.savefig(f'fit_{Data.q2bin}.png')
    plt.close()
# --------------------------
def main():
    '''
    Start here
    '''
    _parse_args()
    _set_logs()
    EnableImplicitMT(10)

    data = _get_data()
    pdf  = _get_pdf()
    d_cns= _get_constraints(pdf)
    print_pdf(pdf=pdf, d_const=d_cns, txt_path=f'./pdf_{Data.q2bin}.txt')

    _fit(pdf=pdf, data=data, constraints=d_cns)
# --------------------------
if __name__ == '__main__':
    main()
