# Build and inspect the v4 ACM draft

Prepared November 27, 2026 on draft PR #29's existing `codex/paper-evidence-draft` worktree, HEAD `d561789f34584d5008457b3efd86dbb738b957ed`, with preserved uncommitted work. The supplied v3 PDF has ten pages. V4 removes intermediate section float barriers and the forced reference-page break, reflows tables at the normal class text size and adds checked related work. Methods, numerical results and image pixels are preserved. The local build and its exact PDF hash are recorded separately in `paper-v4-preparation-2026-11-27/v4-verification.json` in the ChatGPT workspace. The local v4 PDF has eight pages; references begin on page8, which also contains main text. This is a draft, not submission approval.

## Upload and build

1. Upload `corner-scouting-overleaf-source-v4-2026-11-27.zip` from the separate `paper-v4-preparation-2026-11-27/` folder as a **new Overleaf project**, preserving the existing project. ZIP root contains `main.tex`, `references.bib`, `figures.tex`, `tables.tex` and these Markdown guides; `tables/` has seven fragments and `figures/` the unchanged PNG. Do not upload raw data, outputs or reviewer sheets. Markdown links to `../docs/` refer to the repository context; the manuscript itself has no such build dependency.
2. Set the main document to `main.tex`. Keep `\documentclass[sigconf,nonacm]{acmart}`. Do not change geometry, class font sizes or line spacing to affect pagination.
3. Select **XeLaTeX** to match the local engine family, and record the chosen TeX Live version. The local check used Tectonic 0.17.0 (XeTeX), LaTeX2e 2021-11-15 patch level 1 and acmart 1.83 (2022-02-19), with its ACM reference style. Overleaf's newer packages, or pdfLaTeX, may change line breaks and page count. A newer build must be inspected separately; exact output-byte equality is not promised across engines/package versions.
4. Recompile from scratch. Bibliography uses BibTeX via `ACM-Reference-Format`, not Biber. All six keys must resolve: `statsbomb`, `program2026`, `davis2024`, `pappalardo2019`, `wang2024`, `gneiting2007`. StatsBomb has no asserted publication year; explicit `n.d.` avoids the older style's nested-bracket/no-date parsing failure without inventing a date. The note records the actual access date and pinned revision.
5. Inspect the log for missing files, errors, unresolved citations/references and overfull boxes. Tables use natural `\normalsize` text, with no global scaling. The corpus and two primary tables are single-column; the wide sensitivity tables use full-width natural-size panels. Primary targets are grouped rather than repeated in a narrow extra column.
6. Review every rendered page: confirm normal two-column reading order, no orphaned nearly empty left column, continuous systems/dossier text beneath spatial floats, and references after the conclusion in reading order. A single final float barrier preserves reference ordering without forcing a new page. Confirm all figure cells, sample counts and the common 0--6 scale are visible and readable.
7. Download the PDF and full build log into a **new** local output folder; record PDF/source ZIP hashes, engine and package versions. Count pages from that PDF, not from source length. Clarify with the instructor whether references count toward the seven-page requirement; page count alone is not completion. Do not pad spacing or add unverified text.

## Local reproduction

With the portable compiler path adjusted to the actual workspace, run from `paper/`:

```powershell
& "ABSOLUTE_PATH_TO/tectonic.exe" -X compile main.tex `
    --outdir "ABSOLUTE_NEW_BUILD_DIRECTORY" --keep-logs --keep-intermediates
```

Create the output directory first. A normal full TeX distribution can instead run `latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=ABSOLUTE_NEW_BUILD_DIRECTORY main.tex`. The compiler may fetch TeX packages; this is manuscript compilation, not an experiment or provider-data download. Generated files remain outside Git.

## Still pending

Authors, author order and affiliations require confirmation. Additional dossiers covering at least three further distinct teams, independent reader evaluation, scope decisions and owner sign-off remain pending. Related work is now drafted from checked primary publications, but needs subject-owner review. The evidence index distinguishes verified saved bytes from supplied executions. No claim of usefulness, new experiment, accepted proposal deviation or complete submission follows from this build. See [UNRESOLVED.md](UNRESOLVED.md) and [figure-sources.md](figure-sources.md).
