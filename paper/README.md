# ACM sigconf working skeleton

No tracked LaTeX manuscript or bibliography existed on main or draft PR #29 at inspection. `main.tex` is a working skeleton using `acmart` sigconf, `references.bib` contains only records checked against the pinned source/publisher/course brief, and `tables.tex` preserves the six earlier Markdown tables and adds Table 7 for the verified short-threshold sensitivity. The short-threshold section maps to S2 in the evidence index; its saved results were not rerun for paper integration. The Markdown manuscript/evidence index remain the fuller source of qualifications. This is not a compiled, submission-ready or minimum-seven-page paper.

From `paper/`, with a local TeX distribution providing acmart/ACM bibliography style:

```powershell
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=../outputs/paper-build main.tex
```

The output path keeps PDF/auxiliary files separate; use a fresh build directory. No TeX engine or latexmk was found on PATH in this task, so compilation/layout/page count remain unverified. Do not assume the wide draft tables fit; review the rendered PDF and resize/restructure as needed. Full prose, captions, related work, figures, author metadata and final bibliography still need integration. No guessed author identities, venue, performance results or TacticAI bibliography were added. Reconcile changes with `docs/paper-draft.md` and retain its evidence qualifiers.
