# src/

This folder contains the Python source code for the project. Organize code as a small package and modules:

- src/package_name/ - reusable modules (data loading, processing, analysis, plotting)
- src/scripts/ - command-line scripts or entry points used to run end-to-end tasks
- requirements.txt or pyproject.toml at repo root to pin dependencies

Guidelines:
- Keep notebooks for exploration only; put production-ready logic into modules under src/.
- Write unit tests where helpful and document expected inputs/outputs.
