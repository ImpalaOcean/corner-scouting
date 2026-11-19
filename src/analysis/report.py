"""Paper tables, figures and review checks for a finished analysis run (Asaad).

Reads an existing analysis output folder (and, optionally, its window
sensitivity siblings). It never changes the experiment: it rebuilds the per
corner test scores with the alpha and beta recorded in the run, refuses to
continue unless those scores reproduce the saved evaluation exactly, and then
breaks the results down by competition season and by team.

    python -m src.analysis.report --run outputs/analysis_leagues_w15 --output outputs/report_leagues
    python -m src.analysis.report --run outputs/analysis_leagues_w15 --windows outputs/analysis_leagues_w10 outputs/analysis_leagues_w20 outputs/analysis_leagues_uncapped --output outputs/report_leagues

Writes:
  eligibility_by_competition.csv   matches, splits, teams and eligible teams per competition season
  eligibility_teams.csv            every team: training matches and corners, eligible or why not
  results_overall.csv              paired differences for the whole corpus (copied from the run)
  results_by_competition.csv       scores and paired differences per competition season
  window_sensitivity.csv           paired differences per outcome window (with --windows)
  review_checks.json               consistency and methodology checks
  results.md                       the tables above as Markdown, ready for the paper
  fig_paired_differences.png       overall and per competition paired differences, 95% intervals
  fig_team_delivery.png            per team delivery differences, 95% intervals
  fig_window_sensitivity.png       paired differences across windows (with --windows)
"""

import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import random

from .evaluation import (EPSILON, METHODS, SCORED_CATEGORIES, _by_match,
                         _diff_of_sample, _stratum,
                         delivery_probabilities, eligible_teams, fit_history,
                         score_corners)
from .publication import new_output_directory
from .summary import (MIN_CORNERS, MIN_MATCHES, AnalysisError, bootstrap_interval,
                      chronological_splits, load_corners, write_csv)

ALPHA_GRID_MAX = 1000
TARGETS = (('delivery', 'log_loss', 'logloss'), ('shot', 'brier', 'brier'))
# Validated categorical palette (light surface), fixed order by competition id,
# with a distinct marker per slot so identity never rests on colour alone.
COLOURS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300']
MARKERS = ['o', 's', '^', 'D', 'v', 'P']
INK = '#0b0b0b'
INK_MUTED = '#52514e'
GRID = '#e4e3df'


def _read_csv(path):
    with Path(path).open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def _float(value):
    return None if value in (None, '') else float(value)


def load_run(folder):
    folder = Path(folder)
    manifest_path = folder / 'analysis_manifest.json'
    if not manifest_path.exists():
        raise AnalysisError(f'not an analysis output folder: {folder}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('date_cutoff'):
        raise AnalysisError(f'{folder} is a prematch (cutoff) run with no evaluation')
    evaluation = folder / 'evaluation'
    if not evaluation.exists():
        raise AnalysisError(f'{folder} has no evaluation folder')
    return {
        'folder': folder, 'manifest': manifest,
        'summary': _read_csv(evaluation / 'evaluation_summary.csv'),
        'differences': _read_csv(evaluation / 'evaluation_differences.csv'),
        'teams': _read_csv(evaluation / 'team_evaluation.csv'),
        'selection': _read_csv(evaluation / 'alpha_selection.csv'),
    }


def _input_path(run, override=None):
    if override:
        return Path(override)
    path = Path(run['manifest']['input'])
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise AnalysisError(f'input table not found: {path}; pass --input')
    return path


def rebuild(run, input_path):
    """Recreate the split, eligible teams and per corner test records with the
    run's own alpha and beta. Nothing is selected or fitted differently."""
    meta = run['manifest'].get('evaluation') or {}
    alpha, beta = meta.get('alpha'), meta.get('beta')
    rows = load_corners(input_path)
    splits = chronological_splits(rows)
    split_of = {s['match_id']: s['split'] for s in splits}
    by_split = defaultdict(list)
    for r in rows:
        by_split[split_of.get(r['match_id'], 'excluded')].append(r)
    teams = eligible_teams(by_split['train'])
    fit = fit_history(by_split['train'] + by_split['validation'])
    records = score_corners(fit, by_split['test'], teams, alpha, beta)
    return {'rows': rows, 'splits': splits, 'by_split': by_split, 'teams': teams,
            'fit': fit, 'records': records, 'alpha': alpha, 'beta': beta}


def _mean(records, key):
    values = [r[key] for r in records if r[key] is not None]
    return sum(values) / len(values) if values else None


def check_reproduction(run, state):
    """Every overall score must equal the saved one (6 decimals)."""
    saved = {(r['target'], r['method']): _float(r['score']) for r in run['summary']}
    problems = []
    for target, _, prefix in TARGETS:
        for method in METHODS:
            ours = _mean(state['records'], f'{prefix}_{method}')
            theirs = saved.get((target, method))
            if (ours is None) != (theirs is None) or (
                    ours is not None and abs(round(ours, 6) - theirs) > 1e-6):
                problems.append(f'{target}/{method}: rebuilt {ours} vs saved {theirs}')
    if problems:
        raise AnalysisError('rebuilt scores do not match the saved run; refusing to report. '
                            + '; '.join(problems))
    return len(saved)


# Eligibility

def eligibility(state):
    info, stats = {}, defaultdict(lambda: {'train_matches': set(), 'train_corners': 0,
                                           'validation_corners': 0, 'test_corners': 0})
    split_of = {s['match_id']: s['split'] for s in state['splits']}
    for r in state['rows']:
        key = (_stratum(r), r['team_id'])
        info.setdefault(key, {'competition_id': r['competition_id'],
                              'competition_name': r['competition_name'],
                              'season_id': r['season_id'], 'season': r['season'],
                              'team_id': r['team_id'], 'team': r['team']})
        split = split_of.get(r['match_id'])
        if split == 'train':
            stats[key]['train_matches'].add(r['match_id'])
            stats[key]['train_corners'] += 1
        elif split == 'validation':
            stats[key]['validation_corners'] += 1
        elif split == 'test':
            stats[key]['test_corners'] += 1
    team_rows = []
    for key in sorted(info, key=lambda k: (k[0], info[k]['team'])):
        s = stats[key]
        matches, corners = len(s['train_matches']), s['train_corners']
        reasons = []
        if matches < MIN_MATCHES:
            reasons.append(f'train_matches_below_{MIN_MATCHES}')
        if corners < MIN_CORNERS:
            reasons.append(f'train_corners_below_{MIN_CORNERS}')
        team_rows.append(dict(info[key], train_matches=matches, train_corners=corners,
                              validation_corners=s['validation_corners'],
                              test_corners=s['test_corners'],
                              eligible=key in state['teams'],
                              reason=';'.join(reasons) or None))
    comp = defaultdict(lambda: defaultdict(int))
    labels = {}
    for s in state['splits']:
        key = (s['competition_id'], s['season_id'])
        labels[key] = (s['competition_name'], s['season'])
        comp[key]['matches'] += 1
        comp[key][s['split']] += 1
    for t in team_rows:
        key = (t['competition_id'], t['season_id'])
        comp[key]['teams'] += 1
        comp[key]['eligible_teams'] += 1 if t['eligible'] else 0
        comp[key]['corners'] += t['train_corners'] + t['validation_corners'] + t['test_corners']
    comp_rows = []
    for key in sorted(comp):
        c = comp[key]
        comp_rows.append({'competition_id': key[0], 'competition_name': labels[key][0],
                          'season_id': key[1], 'season': labels[key][1],
                          'matches': c['matches'], 'train_matches': c['train'],
                          'validation_matches': c['validation'], 'test_matches': c['test'],
                          'other_matches': c['excluded'] + c['too_few_matches'],
                          'corners': c['corners'], 'teams': c['teams'],
                          'eligible_teams': c['eligible_teams'],
                          'ineligible_teams': c['teams'] - c['eligible_teams']})
    return comp_rows, team_rows


# Results by competition

def _difference_row(label, records, prefix, other, draws, rng):
    used = [r for r in records if r[f'{prefix}_shrunk'] is not None
            and r[f'{prefix}_{other}'] is not None]
    if not used:
        return None, None, None, 0
    diff = sum(r[f'{prefix}_shrunk'] - r[f'{prefix}_{other}'] for r in used) / len(used)
    low, high = bootstrap_interval(_by_match(used),
                                   _diff_of_sample(f'{prefix}_shrunk', f'{prefix}_{other}'),
                                   draws, rng)
    return round(diff, 6), low, high, len(used)


def _verdict(low, high):
    if low is None or high is None:
        return 'unavailable'
    if high < 0:
        return 'shrunk better'
    if low > 0:
        return 'shrunk worse'
    return 'no clear difference'


def by_competition(state, draws, seed):
    rng = random.Random(seed)
    groups = defaultdict(list)
    for r in state['records']:
        groups[r['stratum']].append(r)
    names = {(r['competition_id'], r['season_id']): (r['competition_name'], r['season'])
             for r in state['rows']}
    out = []
    for stratum in sorted(groups):
        records = groups[stratum]
        for target, metric, prefix in TARGETS:
            row = {'competition_id': stratum[0], 'competition_name': names[stratum][0],
                   'season_id': stratum[1], 'season': names[stratum][1],
                   'target': target, 'metric': metric,
                   'teams': len({r['team_id'] for r in records}),
                   'matches': len({r['match_id'] for r in records})}
            for method in METHODS:
                value = _mean(records, f'{prefix}_{method}')
                row[f'score_{method}'] = None if value is None else round(value, 6)
            for other in ('pooled', 'unsmoothed'):
                diff, low, high, n = _difference_row(stratum, records, prefix, other, draws, rng)
                row[f'shrunk_minus_{other}'] = diff
                row[f'shrunk_minus_{other}_ci_low'] = low
                row[f'shrunk_minus_{other}_ci_high'] = high
                row[f'verdict_vs_{other}'] = _verdict(low, high)
                row['corners'] = n
            out.append(row)
    return out


COMPETITION_FIELDS = (['competition_id', 'competition_name', 'season_id', 'season', 'target',
                       'metric', 'teams', 'matches', 'corners']
                      + [f'score_{m}' for m in METHODS]
                      + [f'shrunk_minus_{o}{s}' for o in ('pooled', 'unsmoothed')
                         for s in ('', '_ci_low', '_ci_high')]
                      + ['verdict_vs_pooled', 'verdict_vs_unsmoothed'])
OVERALL_FIELDS = ['target', 'metric', 'comparison', 'difference', 'ci_low', 'ci_high',
                  'verdict', 'corners', 'matches']
WINDOW_FIELDS = ['window', 'target', 'comparison', 'difference', 'ci_low', 'ci_high',
                 'verdict', 'alpha', 'beta', 'corners']


def overall(run):
    out = []
    for r in run['differences']:
        low, high = _float(r['ci_low']), _float(r['ci_high'])
        out.append({'target': r['target'], 'metric': r['metric'],
                    'comparison': r['comparison'], 'difference': _float(r['difference']),
                    'ci_low': low, 'ci_high': high, 'verdict': _verdict(low, high),
                    'corners': r['corners'], 'matches': r['matches']})
    return out


def _window_label(manifest):
    window = manifest.get('window_seconds')
    return 'uncapped' if window is None else f'{float(window):g}s'


def window_table(runs):
    out = []
    for run in runs:
        meta = run['manifest'].get('evaluation') or {}
        for row in overall(run):
            out.append(dict(row, window=_window_label(run['manifest']),
                            alpha=meta.get('alpha'), beta=meta.get('beta')))
    return out


# Review checks

def review_checks(run, state, team_rows):
    meta = run['manifest'].get('evaluation') or {}
    alpha, beta = state['alpha'], state['beta']
    clipped = 0
    scored = 0
    for r in state['by_split']['test']:
        key = (_stratum(r), r['team_id'])
        if key not in state['teams'] or r['delivery_category'] not in SCORED_CATEGORIES:
            continue
        scored += 1
        p = delivery_probabilities(state['fit'], key[0], key[1], 'unsmoothed', alpha or 0)
        if p and p[r['delivery_category']] <= EPSILON * 1.5:
            clipped += 1
    floor = -math.log(EPSILON * 1.5)
    scored_records = [r for r in state['records'] if r['logloss_shrunk'] is not None
                      and r['logloss_unsmoothed'] is not None]
    kept = [r for r in scored_records if r['logloss_unsmoothed'] <= floor]

    def gap(rs):
        if not rs:
            return None
        return round(sum(r['logloss_shrunk'] - r['logloss_unsmoothed'] for r in rs) / len(rs), 6)
    team_eval = run['teams']
    per_team = {}
    for prefix, name in (('logloss', 'delivery'), ('brier', 'shot')):
        low_key = f'{prefix}_diff_ci_low'
        high_key = f'{prefix}_diff_ci_high'
        with_ci = [t for t in team_eval if t.get(low_key) not in (None, '')]
        better = sum(1 for t in with_ci if float(t[high_key]) < 0)
        worse = sum(1 for t in with_ci if float(t[low_key]) > 0)
        per_team[name] = {'teams_with_interval': len(with_ci),
                          'interval_below_zero': better, 'interval_above_zero': worse,
                          'expected_by_chance_each_side': round(0.025 * len(with_ci), 1)}
    return {
        'rebuilt_scores_match_saved_run': True,
        'alpha': alpha, 'beta': beta,
        'alpha_at_grid_max': alpha == ALPHA_GRID_MAX,
        'beta_at_grid_max': beta == ALPHA_GRID_MAX,
        'eligible_teams': len(state['teams']),
        'teams_total': len(team_rows),
        'test_corners': len(state['records']),
        'test_corners_unknown_delivery': sum(1 for r in state['records'] if not r['known']),
        'unsmoothed_clipped_test_corners': clipped,
        'unsmoothed_clipped_share': round(clipped / scored, 4) if scored else None,
        'delivery_shrunk_minus_unsmoothed_all': gap(scored_records),
        'delivery_shrunk_minus_unsmoothed_without_clipped': gap(kept),
        'per_team_intervals': per_team,
        'run_status': run['manifest'].get('status'),
        'run_input_sha256': run['manifest'].get('input_sha256'),
        'run_protocol': run['manifest'].get('evaluation_protocol'),
        'targets': meta.get('targets'),
    }


# Figures

def _style(ax):
    ax.axvline(0, color=INK_MUTED, linewidth=1, zorder=1)
    ax.grid(axis='x', color=GRID, linewidth=0.8, zorder=0)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(INK_MUTED)
    ax.tick_params(colors=INK_MUTED, length=0)


def _competition_style(competition_ids):
    order = sorted(set(competition_ids))
    return {cid: (COLOURS[i % len(COLOURS)], MARKERS[i % len(MARKERS)])
            for i, cid in enumerate(order)}


def figure_paired(overall_rows, comp_rows, path, plt):
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2), sharey=True)
    labels = ['All leagues'] + [r['competition_name'] for r in comp_rows if r['target'] == 'delivery']
    style = _competition_style([r['competition_id'] for r in comp_rows])
    for ax, (target, title) in zip(axes, (('delivery', 'Delivery type (log loss)'),
                                          ('shot', 'Shot creation (Brier score)'))):
        rows = [r for r in overall_rows if r['target'] == target
                and r['comparison'] == 'shrunk_minus_pooled']
        points = [(rows[0]['difference'], rows[0]['ci_low'], rows[0]['ci_high'], INK, 'o')] if rows else []
        for r in comp_rows:
            if r['target'] == target:
                colour, marker = style[r['competition_id']]
                points.append((r['shrunk_minus_pooled'], r['shrunk_minus_pooled_ci_low'],
                               r['shrunk_minus_pooled_ci_high'], colour, marker))
        for y, (value, low, high, colour, marker) in enumerate(points):
            if value is None:
                continue
            ax.plot([low, high], [y, y], color=colour, linewidth=2, solid_capstyle='round', zorder=2)
            ax.scatter([value], [y], color=colour, marker=marker, s=60, zorder=3,
                       edgecolors='white', linewidths=1.5)
        _style(ax)
        ax.set_title(title, color=INK, fontsize=11, loc='left')
        ax.set_xlabel('shrunk minus pooled (below 0 = team history helps)', color=INK_MUTED, fontsize=9)
    axes[0].set_yticks(range(len(labels)))
    axes[0].set_yticklabels(labels, color=INK)
    axes[0].invert_yaxis()
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def figure_teams(team_eval, path, plt):
    rows = [t for t in team_eval if t.get('logloss_shrunk_minus_pooled') not in (None, '')
            and t.get('logloss_diff_ci_low') not in (None, '')]
    rows.sort(key=lambda t: float(t['logloss_shrunk_minus_pooled']))
    style = _competition_style([int(t['competition_id']) for t in rows])
    height = max(4, 0.16 * len(rows) + 1)
    fig, ax = plt.subplots(figsize=(7, height))
    for y, t in enumerate(rows):
        colour, marker = style[int(t['competition_id'])]
        low, high = float(t['logloss_diff_ci_low']), float(t['logloss_diff_ci_high'])
        ax.plot([low, high], [y, y], color=colour, linewidth=1.5, zorder=2)
        ax.scatter([float(t['logloss_shrunk_minus_pooled'])], [y], color=colour,
                   marker=marker, s=28, zorder=3, edgecolors='white', linewidths=1)
    _style(ax)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([t['team'] for t in rows], fontsize=6, color=INK)
    ax.set_xlabel('delivery log loss, shrunk minus pooled (below 0 = team history helps)',
                  color=INK_MUTED, fontsize=9)
    names = {}
    for t in rows:
        names[int(t['competition_id'])] = t['competition_name']
    handles = [plt.Line2D([], [], color=style[c][0], marker=style[c][1], linestyle='',
                          markersize=7, label=names[c]) for c in sorted(names)]
    ax.legend(handles=handles, frameon=False, loc='upper left', fontsize=8)
    ax.set_title('Per team delivery prediction, test matches, 95% match bootstrap',
                 color=INK, fontsize=10, loc='left')
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def figure_windows(window_rows, path, plt):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
    windows = sorted({r['window'] for r in window_rows},
                     key=lambda w: float('inf') if w == 'uncapped' else float(w.rstrip('s')))
    for ax, (target, title) in zip(axes, (('delivery', 'Delivery type (log loss)'),
                                          ('shot', 'Shot creation (Brier score)'))):
        for y, window in enumerate(windows):
            match = [r for r in window_rows if r['window'] == window and r['target'] == target
                     and r['comparison'] == 'shrunk_minus_pooled' and r['difference'] is not None]
            if not match:
                continue
            r = match[0]
            ax.plot([r['ci_low'], r['ci_high']], [y, y], color=COLOURS[0], linewidth=2, zorder=2)
            ax.scatter([r['difference']], [y], color=COLOURS[0], s=60, zorder=3,
                       edgecolors='white', linewidths=1.5)
        _style(ax)
        ax.set_title(title, color=INK, fontsize=11, loc='left')
        ax.set_xlabel('shrunk minus pooled', color=INK_MUTED, fontsize=9)
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
    axes[0].set_yticks(range(len(windows)))
    axes[0].set_yticklabels([f'window {w}' for w in windows], color=INK)
    axes[0].invert_yaxis()
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


# Markdown

def _fmt(value, digits=4):
    return '' if value is None else f'{value:.{digits}f}'


def _ci(low, high):
    return 'n/a' if low is None or high is None else f'[{low:.4f}, {high:.4f}]'


def markdown(overall_rows, comp_rows, comp_elig, window_rows, checks):
    lines = ['# Prediction results', '',
             f"Alpha (delivery) = {checks['alpha']}, beta (shot) = {checks['beta']}, "
             f"{checks['eligible_teams']} of {checks['teams_total']} teams eligible, "
             f"{checks['test_corners']} test corners. Differences are shrunk minus "
             'baseline; below zero means the shrunk team profile predicted better. '
             'Intervals are 95% match bootstrap, pairing both methods on the same corners.', '',
             '## Eligibility by competition season', '',
             '| Competition | Season | Matches | Train / val / test | Corners | Teams | Eligible |',
             '| --- | --- | ---: | --- | ---: | ---: | ---: |']
    for r in comp_elig:
        lines.append(f"| {r['competition_name']} | {r['season']} | {r['matches']} | "
                     f"{r['train_matches']} / {r['validation_matches']} / {r['test_matches']} | "
                     f"{r['corners']} | {r['teams']} | {r['eligible_teams']} |")
    lines += ['', '## Overall paired differences', '',
              '| Target | Comparison | Difference | 95% interval | Verdict |',
              '| --- | --- | ---: | --- | --- |']
    for r in overall_rows:
        lines.append(f"| {r['target']} | {r['comparison']} | {_fmt(r['difference'])} | "
                     f"{_ci(r['ci_low'], r['ci_high'])} | {r['verdict']} |")
    lines += ['', '## By competition season', '',
              '| Competition | Target | Pooled | Unsmoothed | Shrunk | Shrunk minus pooled | 95% interval | Verdict |',
              '| --- | --- | ---: | ---: | ---: | ---: | --- | --- |']
    for r in comp_rows:
        lines.append(f"| {r['competition_name']} | {r['target']} | {_fmt(r['score_pooled'])} | "
                     f"{_fmt(r['score_unsmoothed'])} | {_fmt(r['score_shrunk'])} | "
                     f"{_fmt(r['shrunk_minus_pooled'])} | "
                     f"{_ci(r['shrunk_minus_pooled_ci_low'], r['shrunk_minus_pooled_ci_high'])} | "
                     f"{r['verdict_vs_pooled']} |")
    if window_rows:
        lines += ['', '## Outcome window sensitivity (shrunk minus pooled)', '',
                  '| Window | Target | Difference | 95% interval | Verdict | Alpha | Beta |',
                  '| --- | --- | ---: | --- | --- | ---: | ---: |']
        for r in window_rows:
            if r['comparison'] == 'shrunk_minus_pooled':
                lines.append(f"| {r['window']} | {r['target']} | {_fmt(r['difference'])} | "
                             f"{_ci(r['ci_low'], r['ci_high'])} | {r['verdict']} | "
                             f"{r['alpha']} | {r['beta']} |")
    pt = checks['per_team_intervals']
    lines += ['', '## Review checks', '',
              '* Rebuilt per corner scores reproduce the saved run exactly.',
              f"* Alpha at the top of the grid: {checks['alpha_at_grid_max']}; "
              f"beta at the top of the grid: {checks['beta_at_grid_max']}.",
              f"* Test corners where the unsmoothed baseline gave the observed category "
              f"the floor probability: {checks['unsmoothed_clipped_test_corners']} "
              f"({checks['unsmoothed_clipped_share']}). Delivery shrunk minus unsmoothed is "
              f"{checks['delivery_shrunk_minus_unsmoothed_all']} with them and "
              f"{checks['delivery_shrunk_minus_unsmoothed_without_clipped']} without them, so "
              'that comparison depends on the floor value; the comparison with pooled does not.',
              f"* Per team delivery intervals below zero: {pt['delivery']['interval_below_zero']} "
              f"of {pt['delivery']['teams_with_interval']}; above zero: "
              f"{pt['delivery']['interval_above_zero']} (about "
              f"{pt['delivery']['expected_by_chance_each_side']} per side expected by chance).",
              f"* Per team shot intervals below zero: {pt['shot']['interval_below_zero']} "
              f"of {pt['shot']['teams_with_interval']}; above zero: "
              f"{pt['shot']['interval_above_zero']}.", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, required=True, help='primary analysis output folder')
    parser.add_argument('--input', type=Path, help="override the run's recorded corner table path")
    parser.add_argument('--windows', type=Path, nargs='*', default=[],
                        help='other analysis folders for the window sensitivity table')
    parser.add_argument('--output', type=Path, required=True, help='new folder for the report')
    parser.add_argument('--bootstrap', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=5118)
    args = parser.parse_args()
    try:
        run = load_run(args.run)
        state = rebuild(run, _input_path(run, args.input))
        check_reproduction(run, state)
        comp_elig, team_rows = eligibility(state)
        overall_rows = overall(run)
        comp_rows = by_competition(state, args.bootstrap, args.seed)
        checks = review_checks(run, state, team_rows)
        window_rows = window_table([run] + [load_run(f) for f in args.windows]) if args.windows else []
        with new_output_directory(args.output) as staging:
            write_csv(staging / 'eligibility_by_competition.csv',
                      list(comp_elig[0].keys()) if comp_elig else [], comp_elig)
            write_csv(staging / 'eligibility_teams.csv',
                      list(team_rows[0].keys()) if team_rows else [], team_rows)
            write_csv(staging / 'results_overall.csv', OVERALL_FIELDS, overall_rows)
            write_csv(staging / 'results_by_competition.csv', COMPETITION_FIELDS, comp_rows)
            if window_rows:
                write_csv(staging / 'window_sensitivity.csv', WINDOW_FIELDS, window_rows)
            (staging / 'review_checks.json').write_text(json.dumps(checks, indent=2),
                                                        encoding='utf-8')
            (staging / 'results.md').write_text(
                markdown(overall_rows, comp_rows, comp_elig, window_rows, checks), encoding='utf-8')
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
            except ImportError:
                plt = None
            if plt is not None and comp_rows:
                figure_paired(overall_rows, comp_rows, staging / 'fig_paired_differences.png', plt)
                figure_teams(run['teams'], staging / 'fig_team_delivery.png', plt)
                if window_rows:
                    figure_windows(window_rows, staging / 'fig_window_sensitivity.png', plt)
    except (AnalysisError, FileExistsError) as exc:
        parser.exit(1, f'Report failed: {exc}\n')
    print(f"Report -> {args.output}")
    print(f"{checks['eligible_teams']} of {checks['teams_total']} teams eligible; "
          f"alpha {checks['alpha']}, beta {checks['beta']}")
    for r in overall_rows:
        print(f"  {r['target']:<9}{r['comparison']:<26}{_fmt(r['difference'])}  "
              f"{_ci(r['ci_low'], r['ci_high'])}  {r['verdict']}")


if __name__ == '__main__':
    main()
