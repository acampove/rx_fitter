'''
Script used to plot and tabulate mass scales and resolutions
'''
import os
import re
import json
import argparse

import pandas            as pnd
import matplotlib.pyplot as plt
import pandas            as pnd

from dmu.logging.log_store import LogStore
from dmu.generic           import version_management as vman

log = LogStore.add_logger('rx_fitter:reso_scale')
#------------------------------------------
class Data:
    '''
    Data class
    '''
    fit_dir   = os.environ['FITDIR']
    mc_sample = 'Bu_JpsiK_ee_eq_DPC'
    trigger   = 'Hlt2RD_BuToKpEE_MVA'
    mass      = 'B_M'
    sgregex   = r'sg_.*_(\d)_flt'

    l_brem    = [0, 1, 2]
    l_kind    = ['data', 'mc']
#------------------------------------------
def _name_from_parname(name : str) -> str:
    if name.startswith('mu_'):
        return r'$\mu$'

    mtch = re.match(Data.sgregex, name)
    if not mtch:
        raise ValueError(f'Cannot match {name} as a width with: {Data.sgregex}')

    nsg = mtch.group(1)

    return f'$\sigma_{nsg}$'
#------------------------------------------
def _df_from_pars(d_par : dict[str,list[str]]) -> pnd.DataFrame:
    d_data = {'Parameter' : [], 'Value' : [], 'Error' : []}
    for name, [val, err] in d_par.items():
        if not name.startswith('mu_') and not name.startswith('sg_'):
            continue

        name = _name_from_parname(name)

        d_data['Parameter'].append(name)
        d_data['Value'    ].append(val)
        d_data['Error'    ].append(err)

    df = pnd.DataFrame(d_data)

    return df
#------------------------------------------
def _get_df_fit(kind : str, brem : int) -> pnd.DataFrame:
    sample   = Data.mc_sample if kind == 'mc' else 'DATA'

    inp_path = f'{Data.fit_dir}/{kind}/jpsi'
    inp_path = vman.get_last_version(dir_path=inp_path, version_only=False)
    inp_path = f'{inp_path}/{sample}_{Data.trigger}/{Data.mass}_{brem}/fit.json'

    with open(inp_path, encoding='utf-8') as ifile:
        d_par = json.load(ifile)

    df = _df_from_pars(d_par)

    return df
#------------------------------------------
def _get_df() -> pnd.DataFrame:
    l_df_kind = []
    for kind in Data.l_kind:
        l_df_brem = []
        for brem in Data.l_brem:
            df         = _get_df_fit(kind = kind, brem = brem)
            df['brem'] = brem
            l_df_brem.append(df)

        df = pnd.concat(l_df_brem, axis=0)
        df['kind'] = kind

        l_df_kind.append(df)

    df = pnd.concat(l_df_kind, axis=0)

    return df
#------------------------------------------
def main():
    '''
    Starts here
    '''

    df = _get_df()
    print(df)
#------------------------------------------
if __name__ == '__main__':
    main()
