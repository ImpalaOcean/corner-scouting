# notebooks/

Use notebooks for exploration, visualization, and interactive analysis. Notebooks should:

- Contain exploratory work, visualizations, and example analyses used to build the final deliverables.
- Avoid heavy data dumps — load data using the project's data acquisition scripts.
- Be cleared of large outputs before committing (consider using nbstripout or clearing outputs in CI).

When a notebook contains code that should be reused, move that code into `src/` and keep the notebook as an example or vignette.
