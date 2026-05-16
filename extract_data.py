"""
Extract CM history from Excel and generate cm_history.json
Data source: 0125 to 0525 CM Data.xlsx
Logic:
  - VC (Variable Cost) = AVG FRT + AVG SUR&MISC - AVG CM  (per unit)
  - CM = FRT + SUR&MISC - VC  => when user inputs FRT they can derive CM
  - 40HC CM is per TEU in source; multiply x2 for FEU basis
"""
import json, os, sys
import pandas as pd
import numpy as np
from datetime import datetime

SRC = r'C:\Users\elaineteh\Downloads\0125 to 0525 CM Data.xlsx'
OUT = os.path.join(os.path.dirname(__file__), 'data', 'cm_history.json')

print(f"Reading {SRC} ...")
df = pd.read_excel(SRC, header=[0,1])
df.columns = ['RevWk','TRD','LANE','POR','POL','POD','DEL','DIR','SOC','CNTR_TYPE',
              'GP20_FRT','GP20_SUR','GP20_CM','GP20_VOL','GP20_TTLCM',
              'HC40_FRT','HC40_SUR','HC40_CM','HC40_VOL','HC40_TTLCM',
              'CBP_COST_20','CBP_COST_40']

# Filter GP only (ignore RF/OT/FR)
df = df[df['CNTR_TYPE']=='GP'].copy()

# Numeric coerce
for c in ['GP20_FRT','GP20_SUR','GP20_CM','GP20_VOL','GP20_TTLCM',
          'HC40_FRT','HC40_SUR','HC40_CM','HC40_VOL','HC40_TTLCM',
          'CBP_COST_20','CBP_COST_40']:
    df[c] = pd.to_numeric(df[c], errors='coerce')

# VC = FRT + SUR - CM  (all per TEU/unit)
df['GP20_VC'] = df['GP20_FRT'] + df['GP20_SUR'] - df['GP20_CM']
df['HC40_VC'] = df['HC40_FRT'] + df['HC40_SUR'] - df['HC40_CM']

# Date range
wk_min = int(df['RevWk'].min())
wk_max = int(df['RevWk'].max())

def wk_to_label(w):
    w = str(w)
    yr, wk = int(w[:4]), int(w[4:])
    from datetime import datetime, timedelta
    d = datetime(yr, 1, 4) + timedelta(weeks=wk-1)
    return d.strftime('%Y-%m')

date_range = f"{wk_to_label(wk_min)} ~ {wk_to_label(wk_max)}"
print(f"Date range: {date_range}  |  Total rows: {len(df)}")

# Build lane -> rotation structure
# POR is the actual loading origin (e.g. small feeder port)
# POL is where it gets onto main vessel
# For rotation: use LANE grouping
lane_ports = {}
for lane, grp in df.groupby('LANE'):
    pols = sorted(grp['POL'].dropna().unique().tolist())
    pods = sorted(grp['POD'].dropna().unique().tolist())
    pors = sorted(grp['POR'].dropna().unique().tolist())
    dels = sorted(grp['DEL'].dropna().unique().tolist())
    lane_ports[lane] = {
        'pol': pols,
        'pod': pods,
        'por': pors,
        'del': dels,
        'trd': grp['TRD'].mode()[0] if len(grp) > 0 else '',
        'dir': grp['DIR'].mode()[0] if len(grp) > 0 else '',
    }

# Build port_pair stats (weighted average by volume)
# Group by LANE, POR, POL, POD, DEL
def wavg(vals, weights):
    mask = (~np.isnan(vals)) & (~np.isnan(weights)) & (weights > 0)
    if mask.sum() == 0:
        return np.nan
    return np.average(vals[mask], weights=weights[mask])

records = {}
for (lane, por, pol, pod, del_), grp in df.groupby(['LANE','POR','POL','POD','DEL']):
    key = f"{lane}|{por}|{pol}|{pod}|{del_}"

    # 20GP
    gp_vol = grp['GP20_VOL'].fillna(0).values
    gp_frt = grp['GP20_FRT'].values
    gp_sur = grp['GP20_SUR'].values
    gp_cm  = grp['GP20_CM'].values
    gp_vc  = grp['GP20_VC'].values

    gp_avg_frt = wavg(gp_frt, gp_vol)
    gp_avg_sur = wavg(gp_sur, gp_vol)
    gp_avg_cm  = wavg(gp_cm,  gp_vol)
    gp_avg_vc  = wavg(gp_vc,  gp_vol)
    gp_ttl_vol = float(gp_vol.sum())

    # 40HC
    hc_vol = grp['HC40_VOL'].fillna(0).values
    hc_frt = grp['HC40_FRT'].values
    hc_sur = grp['HC40_SUR'].values
    hc_cm  = grp['HC40_CM'].values
    hc_vc  = grp['HC40_VC'].values

    hc_avg_frt = wavg(hc_frt, hc_vol)
    hc_avg_sur = wavg(hc_sur, hc_vol)
    hc_avg_cm  = wavg(hc_cm,  hc_vol)
    hc_avg_vc  = wavg(hc_vc,  hc_vol)
    hc_ttl_vol = float(hc_vol.sum())

    # 40HC FEU basis (x2)
    hc_avg_cm_feu = hc_avg_cm * 2 if not np.isnan(hc_avg_cm) else np.nan
    hc_avg_vc_feu = hc_avg_vc * 2 if not np.isnan(hc_avg_vc) else np.nan
    hc_avg_frt_feu = hc_avg_frt * 2 if not np.isnan(hc_avg_frt) else np.nan
    hc_avg_sur_feu = hc_avg_sur * 2 if not np.isnan(hc_avg_sur) else np.nan

    weeks_active = int(grp['RevWk'].nunique())

    def safe(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return round(float(v), 2)

    records[key] = {
        'lane': lane,
        'por': por,
        'pol': pol,
        'pod': pod,
        'del': del_,
        'weeks': weeks_active,
        'gp20': {
            'vol': safe(gp_ttl_vol),
            'avg_frt': safe(gp_avg_frt),
            'avg_sur': safe(gp_avg_sur),
            'avg_vc':  safe(gp_avg_vc),
            'avg_cm':  safe(gp_avg_cm),
        },
        'hc40': {
            'vol': safe(hc_ttl_vol),
            'avg_frt': safe(hc_avg_frt),       # per TEU
            'avg_sur': safe(hc_avg_sur),        # per TEU
            'avg_vc':  safe(hc_avg_vc),         # per TEU
            'avg_cm':  safe(hc_avg_cm),         # per TEU
            'avg_frt_feu': safe(hc_avg_frt_feu),  # per FEU
            'avg_sur_feu': safe(hc_avg_sur_feu),
            'avg_vc_feu':  safe(hc_avg_vc_feu),
            'avg_cm_feu':  safe(hc_avg_cm_feu),   # per FEU (x2)
        }
    }

print(f"Total port-pair records: {len(records)}")

# Build transshipment map: POD -> list of DEL that differ from POD
ts_map = {}
for r in records.values():
    pod, del_ = r['pod'], r['del']
    if pod != del_:
        if pod not in ts_map:
            ts_map[pod] = set()
        ts_map[pod].add(del_)
ts_map = {k: sorted(list(v)) for k, v in ts_map.items()}
print(f"Transshipment hubs: {list(ts_map.keys())[:15]}")

# Lane rotations: for each lane, derive common rotation order
# Use the order: POL ports by average voyage sequence
# We'll just list them in DIR order (WB=west-to-east, EB=east-to-west etc.)
lane_info = {}
for lane, lp in lane_ports.items():
    lane_recs = [r for r in records.values() if r['lane']==lane]
    total_vol = sum((r['gp20']['vol'] or 0) + (r['hc40']['vol'] or 0) for r in lane_recs)
    lane_info[lane] = {
        **lp,
        'total_vol': round(total_vol, 0),
        'port_pair_count': len(lane_recs),
    }

out = {
    'metadata': {
        'source': '0125 to 0525 CM Data.xlsx',
        'date_range': date_range,
        'wk_min': wk_min,
        'wk_max': wk_max,
        'total_port_pairs': len(records),
        'generated': datetime.now().isoformat(),
        'note': '40HC avg_cm/avg_frt/avg_vc are per TEU; _feu fields are x2 (per FEU). VC = FRT + SUR - CM',
    },
    'lanes': lane_info,
    'ts_map': ts_map,
    'port_pairs': records,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

sz = os.path.getsize(OUT) / 1024
print(f"\nSaved to {OUT}  ({sz:.1f} KB)")
print("Done.")
