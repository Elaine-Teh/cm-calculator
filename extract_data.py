import pandas as pd
import json

df = pd.read_excel(r'C:\Users\elaineteh\Downloads\0225 to 0526 CM for REX.xlsx', header=[0,1])

# Only keep first 17 meaningful columns
df = df.iloc[:, :17]
df.columns = ['RevMonth','Lane','VVD','SUL','POR','POL','POD','DEL',
               'GP20_TEU','GP20_CM','GP20_PTCM',
               'HC40_TEU','HC40_CM','HC40_PTCM',
               'TOT_TEU','TOT_CM','TOT_PTCM']

print("Columns:", list(df.columns))
print(f"Rows: {len(df)}")

# Fill numeric columns with 0
for col in ['GP20_TEU','GP20_CM','GP20_PTCM','HC40_TEU','HC40_CM','HC40_PTCM','TOT_TEU','TOT_CM','TOT_PTCM']:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

pol_list = sorted(df['POL'].dropna().unique().tolist())
pod_list = sorted(df['POD'].dropna().unique().tolist())
del_list = sorted(df['DEL'].dropna().unique().tolist())
por_list = sorted(df['POR'].dropna().unique().tolist())

print(f"POLs: {len(pol_list)}, PODs: {len(pod_list)}, DELs: {len(del_list)}, PORs: {len(por_list)}")

# Build port pair data: POL -> POD -> DEL
port_pair_data = {}

for (pol, pod, del_val), grp in df.groupby(['POL','POD','DEL'], dropna=False):
    if pd.notna(del_val):
        key = f"{pol}|{pod}|{del_val}"
    else:
        key = f"{pol}|{pod}"

    gp20_sub = grp[grp['GP20_TEU'] > 0]
    hc40_sub = grp[grp['HC40_TEU'] > 0]

    record = {
        'pol': pol,
        'pod': pod,
        'del': str(del_val) if pd.notna(del_val) else '',
        'months': int(len(grp)),
        'gp20': None,
        'hc40': None
    }

    if len(gp20_sub) > 0:
        record['gp20'] = {
            'total_teu': int(gp20_sub['GP20_TEU'].sum()),
            'total_cm': round(float(gp20_sub['GP20_CM'].sum()), 2),
            'avg_ptcm': round(float(gp20_sub['GP20_CM'].sum() / gp20_sub['GP20_TEU'].sum()), 2),
            'avg_per_month_teu': round(float(gp20_sub['GP20_TEU'].sum() / len(gp20_sub)), 1),
            'avg_per_month_cm': round(float(gp20_sub['GP20_CM'].sum() / len(gp20_sub)), 2),
            'months_active': int(len(gp20_sub))
        }

    if len(hc40_sub) > 0:
        record['hc40'] = {
            'total_teu': int(hc40_sub['HC40_TEU'].sum()),
            'total_cm': round(float(hc40_sub['HC40_CM'].sum()), 2),
            'cm_feu': round(float(hc40_sub['HC40_CM'].sum() * 2), 2),
            'avg_ptcm': round(float(hc40_sub['HC40_CM'].sum() / hc40_sub['HC40_TEU'].sum()), 2),
            'avg_ptcm_feu': round(float(hc40_sub['HC40_CM'].sum() * 2 / hc40_sub['HC40_TEU'].sum()), 2),
            'avg_per_month_teu': round(float(hc40_sub['HC40_TEU'].sum() / len(hc40_sub)), 1),
            'avg_per_month_cm': round(float(hc40_sub['HC40_CM'].sum() / len(hc40_sub)), 2),
            'months_active': int(len(hc40_sub))
        }

    port_pair_data[key] = record

# Build AI insight data
ai_data = {
    'best_gp20_pairs': [],
    'best_hc40_pairs': [],
    'gp20_better_than_hc40': [],
    'hc40_better_than_gp20': []
}

qualified = {}
for k, v in port_pair_data.items():
    if v['gp20'] and v['hc40'] and v['gp20']['months_active'] >= 3 and v['hc40']['months_active'] >= 3:
        qualified[k] = v

print(f"Qualified pairs (both EQ, >=3 months): {len(qualified)}")

# Top GP20 by PTCM
sorted_gp20 = sorted(qualified.items(), key=lambda x: x[1]['gp20']['avg_ptcm'], reverse=True)[:15]
for k, v in sorted_gp20:
    ai_data['best_gp20_pairs'].append({
        'pair': k, 'ptcm': v['gp20']['avg_ptcm'], 'months': v['gp20']['months_active']
    })

# Top HC40 FEU by PTCM
sorted_hc40 = sorted(qualified.items(), key=lambda x: x[1]['hc40']['avg_ptcm_feu'], reverse=True)[:15]
for k, v in sorted_hc40:
    ai_data['best_hc40_pairs'].append({
        'pair': k, 'ptcm_feu': v['hc40']['avg_ptcm_feu'], 'months': v['hc40']['months_active']
    })

# GP20 better than HC40 FEU
ratio_gp20_better = sorted(
    [(k, v) for k, v in qualified.items() if v['hc40']['avg_ptcm_feu'] > 0],
    key=lambda x: x[1]['gp20']['avg_ptcm'] / x[1]['hc40']['avg_ptcm_feu'],
    reverse=True
)[:10]
for k, v in ratio_gp20_better:
    ai_data['gp20_better_than_hc40'].append({
        'pair': k,
        'ratio': round(v['gp20']['avg_ptcm'] / v['hc40']['avg_ptcm_feu'], 2),
        'gp20_ptcm': v['gp20']['avg_ptcm'],
        'hc40_ptcm_feu': v['hc40']['avg_ptcm_feu']
    })

# HC40 FEU better than GP20
ratio_hc40_better = sorted(
    [(k, v) for k, v in qualified.items() if v['gp20']['avg_ptcm'] > 0],
    key=lambda x: x[1]['hc40']['avg_ptcm_feu'] / x[1]['gp20']['avg_ptcm'],
    reverse=True
)[:10]
for k, v in ratio_hc40_better:
    ai_data['hc40_better_than_gp20'].append({
        'pair': k,
        'ratio': round(v['hc40']['avg_ptcm_feu'] / v['gp20']['avg_ptcm'], 2),
        'gp20_ptcm': v['gp20']['avg_ptcm'],
        'hc40_ptcm_feu': v['hc40']['avg_ptcm_feu']
    })

# DEL distribution for each POD
del_by_pod = {}
for pod in pod_list:
    pod_df = df[df['POD'] == pod]
    dels = pod_df.groupby('DEL').agg(
        teu=('TOT_TEU','sum'), cm=('TOT_CM','sum'), rows=('TOT_TEU','count')
    ).reset_index()
    del_by_pod[pod] = [
        {'del': str(r['DEL']) if pd.notna(r.get('DEL','')) else '', 'teu': int(r['teu']), 'cm': round(float(r['cm']),2), 'rows': int(r['rows'])}
        for _, r in dels.sort_values('cm', ascending=False).iterrows()
    ]

output = {
    'pol_list': pol_list,
    'pod_list': pod_list,
    'del_list': del_list,
    'por_list': por_list,
    'port_pairs': port_pair_data,
    'ai_insights': ai_data,
    'del_by_pod': del_by_pod,
    'metadata': {
        'total_records': len(df),
        'period': '2025-02 to 2026-05',
        'total_teu': int(df['TOT_TEU'].sum()),
        'total_cm': round(float(df['TOT_CM'].sum()), 2),
        'total_gp20_teu': int(df['GP20_TEU'].sum()),
        'total_hc40_teu': int(df['HC40_TEU'].sum()),
        'overall_gp20_ptcm': round(float(df['GP20_CM'].sum() / df['GP20_TEU'].sum()), 2),
        'overall_hc40_ptcm': round(float(df['HC40_CM'].sum() / df['HC40_TEU'].sum()), 2),
        'overall_hc40_ptcm_feu': round(float(df['HC40_CM'].sum() * 2 / df['HC40_TEU'].sum()), 2),
    }
}

import os
out_dir = r'c:\Users\elaineteh\WorkBuddy\20260515150853\cm_calculator\data'
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'cm_history.json')

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)

print(f"\nGenerated: {out_path}")
print(f"  File size: {os.path.getsize(out_path)/1024:.1f} KB")
