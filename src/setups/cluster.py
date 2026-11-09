"""Deterministic grouping of static setups, with a stability check.

Pure Python (no extra dependencies). Same input -> same output: items are
ordered by the caller, initial centres are chosen by farthest-point rule with
index tie-breaks, and the stability check uses a seeded random generator.
Identical setup vectors always receive the same cluster.
"""

import random


def sq_dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def nearest(point, centers):
    return min(range(len(centers)), key=lambda c: (sq_dist(point, centers[c]), c))


def initial_centers(vectors, k):
    n = len(vectors)
    mean = [sum(col) / n for col in zip(*vectors)]
    first = min(range(n), key=lambda i: (sq_dist(vectors[i], mean), i))
    chosen = [first]
    while len(chosen) < k:
        far = max(
            range(n),
            key=lambda i: (min(sq_dist(vectors[i], vectors[c]) for c in chosen), -i),
        )
        chosen.append(far)
    return [list(vectors[i]) for i in chosen]


def kmeans(vectors, k, max_iter=100):
    """Return (labels, centers). k is capped at the number of distinct vectors."""
    k = max(1, min(k, len({tuple(v) for v in vectors})))
    centers = initial_centers(vectors, k)
    labels = [nearest(v, centers) for v in vectors]
    for _ in range(max_iter):
        for c in range(k):
            members = [vectors[i] for i, lab in enumerate(labels) if lab == c]
            if members:
                centers[c] = [sum(col) / len(members) for col in zip(*members)]
        new = [nearest(v, centers) for v in vectors]
        if new == labels:
            break
        labels = new
    return relabel(labels, centers)


def relabel(labels, centers):
    """Number clusters by size (largest first), ties by centre, dropping empties."""
    sizes = {}
    for lab in labels:
        sizes[lab] = sizes.get(lab, 0) + 1
    order = sorted(sizes, key=lambda c: (-sizes[c], tuple(centers[c])))
    mapping = {old: new for new, old in enumerate(order)}
    return [mapping[lab] for lab in labels], [centers[old] for old in order]


def adjusted_rand_index(a, b):
    """Agreement of two labellings, ignoring label names (1 = identical)."""
    n = len(a)
    if n < 2:
        return 1.0
    pairs = lambda m: m * (m - 1) / 2
    table, rows, cols = {}, {}, {}
    for x, y in zip(a, b):
        table[(x, y)] = table.get((x, y), 0) + 1
        rows[x] = rows.get(x, 0) + 1
        cols[y] = cols.get(y, 0) + 1
    index = sum(pairs(v) for v in table.values())
    row_sum = sum(pairs(v) for v in rows.values())
    col_sum = sum(pairs(v) for v in cols.values())
    expected = row_sum * col_sum / pairs(n)
    maximum = (row_sum + col_sum) / 2
    if maximum == expected:
        return 1.0
    return (index - expected) / (maximum - expected)


def stability(vectors, labels, k, runs=10, fraction=0.8, seed=0):
    """Mean ARI between the full clustering and re-clusterings of random 80%
    subsamples (all points then assigned to the nearest subsample centre).
    None when there is too little data (fewer than 10 corners per cluster)
    or only one cluster."""
    n = len(vectors)
    if k < 2 or len(set(labels)) < 2 or n < 10 * k:
        return None
    size = max(k, round(fraction * n))
    scores = []
    for run in range(runs):
        rng = random.Random(seed + run)
        subset = sorted(rng.sample(range(n), size))
        _, centers = kmeans([vectors[i] for i in subset], k)
        again = [nearest(v, centers) for v in vectors]
        scores.append(adjusted_rand_index(labels, again))
    return round(sum(scores) / len(scores), 4)
