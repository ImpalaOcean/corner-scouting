# configs/

Store shared configuration used by scripts and notebooks here (e.g., `config.yaml` or `settings.toml`).

Suggested contents:
- Paths for raw and processed data (these should be in `.gitignore` and not committed with large files)
- Plotting/style defaults
- Feature flags for analyses

Do not store secrets (API keys or credentials) in this directory; use environment variables or a secure secret store.
