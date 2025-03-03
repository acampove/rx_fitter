'''
Module with functions needed to provide fit components
'''
# pylint: disable=too-many-positional-arguments, too-many-function-args, too-many-arguments, too-many-locals

import os
import copy

from zfit.core.interfaces                        import ZfitSpace as zobs
from ROOT                                        import RDataFrame
from dmu.generic                                 import version_management as vman
from dmu.stats.model_factory                     import ModelFactory
from dmu.logging.log_store                       import LogStore
from rx_selection                                import selection as sel
from rx_data.rdf_getter                          import RDFGetter
from rx_calibration.hltcalibration.fit_component import FitComponent
from rx_fitter.mc_par_pdf                        import MCParPdf
from rx_fitter.prec                              import PRec

log = LogStore.add_logger('rx_fitter:components')
# ------------------------------------
class Data:
    '''
    Data class
    '''
    cache_dir = '/tmp/cache/rx_fits'
# ---------------------------------
def get_rdf(sample : str, q2bin : str, trigger : str, cuts : dict[str,str] = None) -> RDataFrame:
    '''
    Function that returns a ROOT dataframe for a given dataset, MC or real data
    '''
    out_path = f'{Data.cache_dir}/{sample}_{q2bin}.root'
    if os.path.isfile(out_path):
        log.info('DataFrame already cached, reloading')
        rdf = RDataFrame('tree', out_path)
        return rdf

    log.info('DataFrame not cached')

    gtr = RDFGetter(sample=sample, trigger=trigger)
    rdf = gtr.get_rdf()
    rdf = rdf.Define('nbrem', 'L1_BremMultiplicity + L2_BremMultiplicity')

    analysis = 'MM' if 'MuMu' in trigger else 'EE'

    d_sel=sel.selection(project='RK', analysis=analysis, q2bin=q2bin, process=sample)
    d_sel.update(cuts)
    for cut_name, cut_value in d_sel.items():
        log.info(f'{cut_name:<20}{cut_value}')
        rdf = rdf.Filter(cut_value, cut_name)

    if cuts is not None:
        log.warning('Overriding default selection')
        for name, expr in cuts.items():
            log.info(f'   {name:<20}{expr}')
            rdf = rdf.Filter(expr, name)

    rep = rdf.Report()
    rep.Print()

    return rdf
# ------------------------------------
def _cuts_from_conf(nbrem : int, cfg : dict) -> dict[str,str]:
    bcut  = cfg['brem'][nbrem]
    d_cut = {'nbrem' : bcut}
    cuts  = cfg['input']['selection']
    d_cut.update(cuts)

    return d_cut
# ------------------------------------
def get_mc(obs : zobs, component_name : str, nbrem : int, cfg : dict) -> FitComponent:
    '''
    Will return FitComponent object for given MC sample
    '''
    cfg     = copy.deepcopy(cfg)
    cuts    = _cuts_from_conf(nbrem, cfg)

    d_inp   = cfg['input']
    trigger = d_inp['trigger']
    q2bin   = d_inp['q2bin'  ]

    d_cmp   = cfg['fitting']['config'][component_name]
    d_fit   = d_cmp['fitting']
    d_plt   = d_cmp['plotting']

    sample  = d_cmp['sample']
    rdf     = get_rdf(sample, q2bin, trigger, cuts)
    rdf     = rdf.Define('weights', '1')

    cfg['component_name'] = component_name
    cfg['q2bin'  ]        = q2bin
    cfg['trigger']        = trigger
    cfg['nbrem'  ]        = nbrem

    cmp_cfg         = cfg['components'][component_name][nbrem]
    cfg['fvers'   ] = cmp_cfg['fvers'  ]
    cfg['create'  ] = cmp_cfg['create' ]
    cfg['shared'  ] = cmp_cfg['shared' ]
    cfg['model'   ] = cmp_cfg['model'  ]
    cfg['pfloat'  ] = cmp_cfg['pfloat' ]
    cfg['fitting' ] = d_fit
    cfg['plotting'] = d_plt
    cfg['fitting']['weights_column'] = cmp_cfg['weights']

    obj   = MCParPdf(rdf=rdf, obs=obs, cfg=cfg)

    return obj.get_fcomp()
# ------------------------------------
def get_prc(obs : zobs, nbrem : int, cfg : dict) -> FitComponent:
    '''
    Function returning FitComponent object for Partially reconstructed background
    '''
    mass     = obs.obs[0]
    q2bin    = cfg['input']['q2bin']
    trigger  = cfg['input']['trigger']
    l_path   = cfg['input']['samples']
    bw       = cfg['fitting']['config']['PRec']['bw']
    l_samp   = cfg['fitting']['config']['PRec']['sample']
    d_wgt    = cfg['fitting']['config']['PRec']['weights']

    RDFGetter.samples = l_path

    obj      = PRec(samples=l_samp, trig=trigger, q2bin=q2bin, d_weight=d_wgt)
    obj.cuts = _cuts_from_conf(nbrem, cfg)

    pdf=obj.get_sum(mass=mass, name='PRec', obs=obs, bandwidth=bw)

    cfg['name']    = 'PRec'

    fcm= FitComponent(cfg=cfg, rdf=None, pdf=pdf)

    return fcm
# ------------------------------------
def get_cb(obs : zobs, kind : str) -> FitComponent:
    '''
    Returns fit component for combinatorial fit
    '''
    mod = ModelFactory(preffix='cmb', obs=obs, l_pdf = [kind], l_shared = [], l_float= [])
    pdf = mod.get_pdf()

    cfg = {
            'name'    : f'cmb_{kind}',
            'out_dir' : f'/tmp/cmb_{kind}',
            }

    obj   = FitComponent(cfg=cfg, rdf=None, pdf=pdf, obs=obs)
    obj.run()

    return obj
# ------------------------------------
