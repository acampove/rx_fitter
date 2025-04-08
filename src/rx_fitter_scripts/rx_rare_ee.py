'''
Script used to fit the rare mode
'''
from importlib.resources import files

import yaml
import zfit
from zfit.core.data         import Data       as zdata
from zfit.core.basepdf      import BasePDF    as zpdf
from zfit.core.interfaces   import ZfitSpace  as zobs
from zfit.core.parameter    import Parameter  as zpar
from dmu.stats.fitter       import Fitter
from dmu.logging.log_store  import LogStore
from rx_data.rdf_getter     import RDFGetter
from rx_selection           import selection  as sel
from rx_fitter              import components as cmp

log=LogStore.add_logger('rx_fitter:rx_rare_ee')
# --------------------------
class Data:
    '''
    Data class
    '''
    sample  : str  = 'DATA*'
    trigger : str  = 'Hlt2RD_BuToKpEE_MVA'
    version : str  = 'v1'
    q2bin   : str  = 'central'
    mass    : str  = 'B_M_brem_track_2'
    minx    : int  = 4_500
    maxx    : int  = 6_000
    obs     : zobs = zfit.Space(mass, limits=(minx, maxx))
    nsig    : zpar = zfit.Parameter('nsig', 0, 0, 10_000)

    l_pdf   : list[zpdf] = []
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
def _add_pdf_prc(sample : str) -> None:
    cfg                   = _load_config(component='bxhsee')
    cfg['input']['q2bin'] = Data.q2bin

    pdf  = cmp.get_kde(obs=Data.obs, sample=sample, nbrem=None, cfg=cfg)
    scale= zfit.Parameter(f's{sample}', 0, 0, 10)
    nprc = zfit.ComposedParameter(f'n{sample}', lambda x : x['nsig'] * x['scale'], params={'nsig' : Data.nsig, 'scale' : scale})
    pdf  = pdf.create_extended(nprc)

    Data.l_pdf.append(pdf)
# --------------------------
def _add_pdf_leak(sample : str) -> None:
    cfg                   = _load_config(component='ccbar_leak')
    cfg['input']['q2bin'] = Data.q2bin

    pdf = cmp.get_kde(obs=Data.obs, sample=sample, nbrem=None, cfg=cfg)

    Data.l_pdf.append(pdf)
# --------------------------
def _add_pdf_sig() -> None:
    cfg  = _load_config(component='signal')
    pdf  = cmp.get_mc_reparametrized(obs=Data.obs, component_name='Signal', cfg=cfg, nbrem=None)
    pdf  = pdf.create_extended(Data.nsig)

    Data.l_pdf.append(pdf)
# --------------------------
def _get_pdf() -> zpdf:
    _add_pdf_cmb()
    _add_pdf_sig()
    _add_pdf_prc(sample='Bu_Kstee_Kpi0_eq_btosllball05_DPC')
    _add_pdf_prc(sample='Bd_Kstee_eq_btosllball05_DPC')

    if Data.q2bin == 'central':
        _add_pdf_leak(sample='Bu_JpsiK_ee_eq_DPC')

    if Data.q2bin == 'high':
        _add_pdf_prc(sample='Bs_phiee_eq_Ball_DPC')

    pdf = zfit.pdf.SumPDF(Data.l_pdf)

    return pdf
# --------------------------
def _get_data() -> zdata:
    gtr = RDFGetter(sample=Data.sample, trigger=Data.trigger)
    rdf = gtr.get_rdf()
    rdf = sel.apply_full_selection(rdf=rdf, project='RK', trigger=Data.trigger, q2bin=Data.q2bin, process=Data.sample)

    arr_mass = rdf.AsNumpy([Data.mass])[Data.mass]
    data     = zfit.Data.from_numpy(obs=Data.obs, array=arr_mass)

    return data
# --------------------------
def main():
    '''
    Start here
    '''
    pdf  = _get_pdf()
    data = _get_data()

    obj = Fitter(pdf=pdf, data=data)
    res = obj.fit()
# --------------------------
if __name__ == '__main__':
    main()
