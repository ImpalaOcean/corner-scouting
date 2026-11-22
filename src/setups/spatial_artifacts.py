"""Build the sensitivity table and the two figures for docs/spatial-results.md.

Needs matplotlib: python -m pip install -r src/setups/requirements-figures.txt
Run from the repository root, e.g.:
  python -m src.setups.spatial_artifacts --out docs/spatial-results ...
Run folders are given as --run LABEL=FOLDER (one per setup run) plus --primary and --teams.
"""

import argparse, csv, json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("--run", action="append", default=[], help="LABEL=setup run folder")
ap.add_argument("--primary", required=True, help="setup run folder for the primary k=4 figure")
ap.add_argument("--teams", required=True, help="outputs/...-shared-clusters folder")
ap.add_argument("--out", required=True, type=Path)
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)

# 1. Sensitivity table, read straight from each setup_report.json
rows = []
for item in a.run:
    label, folder = item.rsplit("=", 1)
    rep = json.loads((Path(folder) / "setup_report.json").read_text(encoding="utf-8"))
    rows.append(dict(setting=label, folder=folder, usable=rep.get("corners_usable"),
                     clusters=len(rep["clusters"]),
                     sizes="/".join(str(c["size"]) for c in rep["clusters"]),
                     stability_ari=rep.get("stability_ari"), exploratory=rep.get("exploratory"),
                     caveats="; ".join(rep.get("caveats", []))))
with (a.out / "sensitivity.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("| Setting | Usable | Clusters | Sizes | ARI | Exploratory |\n|---|---|---|---|---|---|")
for r in rows:
    print(f"| {r['setting']} | {r['usable']} | {r['clusters']} | {r['sizes']} | {r['stability_ari']} | {r['exploratory']} |")

# 2. Figure 1: mean players per zone for each primary cluster
rep = json.loads((Path(a.primary) / "setup_report.json").read_text(encoding="utf-8"))
cl = rep["clusters"]
fig, axes = plt.subplots(2, len(cl), figsize=(3*len(cl), 6.2))
for j, c in enumerate(cl):
    for i, (key, title) in enumerate((("mean_attackers_by_zone", "attackers"),
                                       ("mean_defenders_by_zone", "defenders"))):
        ax = axes[i][j]
        grid = [[c[key][str(3*r + k + 1)] for k in range(3)] for r in range(3)]
        im = ax.imshow(grid, vmin=0, vmax=6, cmap="Blues")
        for r in range(3):
            for k in range(3):
                ax.text(k, r, f"z{3*r+k+1}\n{grid[r][k]:.2f}", ha="center", va="center", fontsize=8,
                        color="white" if grid[r][k] > 3.5 else "black")
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"Cluster {c['cluster_id']} (n={c['size']}) {title}", fontsize=9)
fig.colorbar(im, ax=axes, shrink=0.6, label="mean outfield players per corner")
fig.suptitle("Figure 1. Mean players per penalty-box zone, pooled k=4 clusters (exploratory)", fontsize=10)
fig.savefig(a.out / "figure1_cluster_zone_means.png", dpi=200); plt.close(fig)

# 3. Figure 2: each team's share of the shared clusters
prof = list(csv.DictReader((Path(a.teams) / "team_cluster_profiles.csv").open(encoding="utf-8-sig")))
teams = {}
for r in prof:
    key = (r["competition_name"], r["team"])
    t = teams.setdefault(key, dict(n=int(r["eligible_team_corners"]), shares={}))
    t["shares"][int(r["cluster_id"])] = float(r["cluster_share"]) if r["cluster_share"] else 0.0
order = sorted(teams, key=lambda k: (-teams[k]["n"], k))
ids = sorted({i for t in teams.values() for i in t["shares"]})
fig, ax = plt.subplots(figsize=(8, 0.22*len(order) + 1.5))
left = [0.0]*len(order)
for i in ids:
    vals = [teams[k]["shares"].get(i, 0.0) for k in order]
    ax.barh(range(len(order)), vals, left=left, label=f"cluster {i}")
    left = [l + v for l, v in zip(left, vals)]
ax.set_yticks(range(len(order)))
ax.set_yticklabels([f"{k[1]} ({'WC' if 'World' in k[0] else 'Euro'}, n={teams[k]['n']})" for k in order], fontsize=6)
ax.invert_yaxis(); ax.set_xlim(0, 1); ax.set_xlabel("share of team's usable corners")
ax.legend(ncol=len(ids), fontsize=7, loc="lower center", bbox_to_anchor=(0.5, 1.0))
ax.set_title("Figure 2. Team shares of shared clusters (retrospective, small samples)", fontsize=9, pad=24)
fig.tight_layout(); fig.savefig(a.out / "figure2_team_cluster_shares.png", dpi=200); plt.close(fig)
print("wrote", a.out)
