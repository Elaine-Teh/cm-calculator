# CM Calculator Web Platform

## Location
`c:\Users\elaineteh\WorkBuddy\20260515150853\cm_calculator\`

## Files
- `index.html` — Main web app (single file, no build needed)
- `data/cm_history.json` — Extracted from "0225 to 0526 CM for REX.xlsx"

## How to use
1. Open `index.html` in browser (or run `python -m http.server 8765` in the folder)
2. Select POL, POD, DEL for each port pair
3. Input 20' and 40' BSA (TEU)
4. Click "Calculate CM" to see estimated CM breakdown
5. AI panel shows margin optimization suggestions

## Data source
- 3,203 rows, 2025-02 to 2026-05
- 43 POLs, 38 PODs, 40 DELs
- 80 qualified port pairs (both 20GP and 40HC, >= 3 months history)
- 40' CM displayed in FEU basis (TEU CM x 2)
