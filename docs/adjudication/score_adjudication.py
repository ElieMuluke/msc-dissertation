"""Score the blind adjudication worksheet against the benchmark's labels.

Usage:  python docs/adjudication/score_adjudication.py docs/adjudication/answers.txt

answers.txt: one line per case, "<alert_id> <E|D|I> <rule> <H|M|L>", e.g.
    TXN-2025-002 E SAN-1 H
Lines starting with # are ignored. Reports raw agreement, Cohen's kappa vs the
benchmark author, agreement split by your confidence, and the per-case table.
"""
import json, sys
from collections import Counter

MAP = {"E": "escalate", "D": "dismiss", "I": "investigate"}
alerts = json.load(open("/home/el/projects/dfah-repo/econometrics/benchmarks/"
                        "compliance_triage/data/alerts.json"))["alerts"]
labels = {c["alert_id"]: c["ground_truth"] for c in alerts}

rows = []
for line in open(sys.argv[1] if len(sys.argv) > 1 else "docs/adjudication/answers.txt"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    parts = line.split()
    aid, dec = parts[0], MAP.get(parts[1].upper(), parts[1])
    rule = parts[2] if len(parts) > 2 else ""
    conf = parts[3].upper() if len(parts) > 3 else "?"
    rows.append((aid, dec, rule, conf, labels[aid]))

n = len(rows)
agree = sum(1 for r in rows if r[1] == r[4])
print(f"cases adjudicated: {n}")
print(f"raw agreement with benchmark labels: {agree}/{n} = {agree/n:.2f}\n")

# Cohen's kappa (two raters, nominal, 3 categories)
cats = ["escalate", "dismiss", "investigate"]
po = agree / n
mine, theirs = Counter(r[1] for r in rows), Counter(r[4] for r in rows)
pe = sum((mine[c] / n) * (theirs[c] / n) for c in cats)
kappa = (po - pe) / (1 - pe) if pe != 1 else float("nan")
print(f"Cohen's kappa = {kappa:.3f}   (chance agreement pe={pe:.3f})")
print("  <0 none · 0-.20 slight · .21-.40 fair · .41-.60 moderate · .61-.80 substantial\n")

for c in ("H", "M", "L"):
    sub = [r for r in rows if r[3] == c]
    if sub:
        a = sum(1 for r in sub if r[1] == r[4])
        print(f"confidence {c}: {a}/{len(sub)} = {a/len(sub):.2f}")

print("\nper-case:")
print(f"{'case':16s} {'you':12s} {'benchmark':12s} {'rule':10s} conf  match")
for aid, dec, rule, conf, lab in rows:
    print(f"{aid:16s} {dec:12s} {lab:12s} {rule:10s} {conf:4s}  {'yes' if dec==lab else 'NO'}")

print("\nyour distribution:  ", dict(mine))
print("benchmark's:        ", dict(theirs))
