"""Refresh report result tables exclusively from completed run artifacts."""

import json
from pathlib import Path

root = Path(__file__).resolve().parent
runs = [
    json.loads(p.read_text())
    for p in sorted((root / "artifacts").glob("*_results.json"))
]
lines = [
    "# Recorded experimental results",
    "",
    "| Market | Seed | Model | Test N | Accuracy % | Balanced accuracy % | Macro F1 | MCC |",
    "|---|---|---|---|---|---|---|---|",
]
for r in runs:
    for name, m in r["models"].items():
        lines.append(
            f"| {r['metadata']['market']} | {r['metadata']['seed']} | {name} | {m['samples']} | {m['accuracy_pct']:.2f} | {m['balanced_accuracy_pct']:.2f} | {m['macro_f1']:.3f} | {m['mcc']:.3f} |"
        )
if not runs:
    lines.append("\nNo completed experiments. No numerical claims are supported.")
(root / "RESULTS.md").write_text("\n".join(lines) + "\n")

from statistics import mean, pstdev
summary=['# Seed variability','', '| Market | Model | Accuracy mean ± SD | Macro-F1 mean ± SD |','|---|---|---|---|']
for market in ['India','US']:
    selected=[r for r in runs if r['metadata']['market']==market]
    if not selected:continue
    for name in selected[0]['models']:
        acc=[r['models'][name]['accuracy_pct'] for r in selected]
        f1=[r['models'][name]['macro_f1'] for r in selected]
        summary.append(f'| {market} | {name} | {mean(acc):.2f} ± {pstdev(acc):.2f} | {mean(f1):.3f} ± {pstdev(f1):.3f} |')
(root/'SEED_SUMMARY.md').write_text('\n'.join(summary)+'\n')
