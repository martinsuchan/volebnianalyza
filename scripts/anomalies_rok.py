"""Mezivýsledky anomalies.py pro zpětně analyzovaný rok (AUDIT_YEAR, např. 2018), které findings_auto/findings_m potřebují a hlavní běh
anomalies.py počítá jen pro 2022 a 2026: metriky okrsků (precinct), záměny stran (swaps) a srovnání lístku města a MČ/MO (cross)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
from common import RES, ROK
import anomalies

if __name__ == '__main__':
    p = f'{RES}/shares_{ROK}.pkl'
    R = pd.read_pickle(p) if os.path.exists(p) else anomalies.share_residuals(ROK)
    anomalies.precinct_metrics(ROK).to_pickle(f'{RES}/precinct_{ROK}.pkl')
    anomalies.swaps(R).to_pickle(f'{RES}/swaps_{ROK}.pkl')
    anomalies.cross_ballot(ROK).to_pickle(f'{RES}/cross_{ROK}.pkl')
    print(ROK, 'precinct/swaps/cross hotovo')
