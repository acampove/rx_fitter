'''
Module with class MCParPdf
'''
# pylint: disable=too-many-positional-arguments, too-many-function-args, too-many-arguments, too-many-locals, too-many-instance-attributes

import os
import json
import copy

from ROOT                                        import RDataFrame
from dmu.logging.log_store                       import LogStore
from dmu.stats.model_factory                     import ModelFactory
from dmu.generic                                 import version_management as vman
from zfit.core.basepdf                           import ZfitPDF            as zpdf
from zfit.core.interfaces                        import ZfitSpace          as zobs
from rx_calibration.hltcalibration.fit_component import FitComponent, load_fit_component

log = LogStore.add_logger('rx_fitter:mc_par_pdf')
# ---------------------------------------
class MCParPdf:
    '''
    Class intended to provide FitComponent instances from fits to MC
    '''
    # ---------------------------------------
    def __init__(
            self,
            rdf    : RDataFrame,
            obs    : zobs,
            cfg    : dict) -> FitComponent:

        self._rdf    = rdf
        self._obs    = obs
        self._cfg    = copy.deepcopy(cfg)
        self._mass   = obs.obs[0]

        self._component_name = self._cfg['component_name']

        self._q2bin       = self._cfg['q2bin'  ]
        self._trigger     = self._cfg['trigger']
        self._nbrem       = self._cfg['nbrem'  ]
        self._create      = self._cfg['create' ]
        self._model       = self._cfg['model'  ]

        self._fit_dir        = cfg['output' ]['fit_dir']
        self._cfg['out_dir'] = self._get_pars_dir()
        self._cfg['name'   ] = self._component_name
    # ---------------------------------------
    def _get_pars_dir(self, version : str = None) -> str:
        model_name = '_'.join(self._model)
        init_dir   = f'{self._fit_dir}/mc/{self._q2bin}'
        fnal_dir   = f'{self._component_name}_{self._trigger}/{self._mass}_{self._nbrem}/{model_name}'

        if version is not None:
            pars_dir = f'{init_dir}/{version}/{fnal_dir}'
            log.debug(f'Using user defined version of fit in: {pars_dir}')
            return pars_dir

        if not os.path.isdir(init_dir):
            init_dir = f'{init_dir}/v1'
            log.info(f'No output directory found, making first version of fit directory in: {init_dir}')
            return f'{init_dir}/{fnal_dir}'

        init_dir = vman.get_last_version(dir_path=init_dir, version_only=False)
        if self._create:
            init_dir = vman.get_next_version(init_dir)
            log.info(f'Creating new version of fit in: {init_dir}')
        else:
            log.info(f'Using latest version of fit in: {init_dir}')

        return f'{init_dir}/{fnal_dir}'
    # ------------------------------------
    def _fix_tails(self, pdf : zpdf, fix_dir : str) -> zpdf:
        if self._cfg['fvers'] is None:
            log.debug('No tail parameter fixing version provided, returning original PDF')
            return pdf

        json_path = f'{fix_dir}/fit.json'
        log.info(40 * '-')
        log.info(f'Fixing parameters with: {json_path}')
        log.info(40 * '-')
        s_par = pdf.get_params()

        with open(json_path, encoding='utf-8') as ifile:
            d_par = json.load(ifile)

        for par in s_par:
            if par.name not in d_par:
                continue

            if par.name.endswith('_flt'):
                continue

            [val, _] = d_par[par.name]

            par.set_value(val)

            log.info(f'{par.name:<30}{"--->":<10}{val:.3f}')
            par.floating = False

        return pdf
    # ---------------------------------------
    def get_fcomp(self) -> FitComponent:
        '''
        Returns instance of FitComponent
        '''
        log.debug(f'Bulding model: {self._model}')
        mod   = ModelFactory(
                obs     = self._obs,
                preffix = self._component_name,
                l_pdf   = self._cfg['model' ],
                l_shared= self._cfg['shared'],
                l_float = self._cfg['pfloat'])

        pdf   = mod.get_pdf()

        obj   = load_fit_component(cfg=self._cfg, pdf=pdf)
        if obj is not None:
            log.info('Will load PDF from cached parameters file')
            return obj

        if 'fvers' in self._cfg:
            fix_dir = self._get_pars_dir(self._cfg['fvers'])
            pdf     = self._fix_tails(pdf=pdf, fix_dir=fix_dir)

        obj     = FitComponent(cfg=self._cfg, rdf=self._rdf, pdf=pdf, obs=self._obs)

        return obj
# ---------------------------------------
