# Contributing

Contributions that improve forecast reliability, validation, testing, documentation, or deployment are welcome.

## Development setup

1. Fork or clone the repository.
2. Create a focused branch from `main`.
3. Create a Python virtual environment.
4. Install development dependencies with `python -m pip install -r requirements-dev.txt`.
5. Run `python scripts/verify.py` before opening a pull request.

## Change guidelines

- Keep commits small, focused, and written in imperative form.
- Add or update tests whenever behavior changes.
- Preserve chronological forecasting semantics and prevent target leakage.
- Keep public model IDs stable unless the API contract intentionally changes.
- Never load untrusted pickle or joblib artifacts.
- Do not commit credentials, virtual environments, caches, or unrelated generated files.

## Data and model changes

Changes to training data, recursive history, feature columns, or model artifacts require extra care:

- Explain the source and date range of new data.
- Preserve an uninterrupted daily history.
- Update `models/model_manifest.json` when the feature schema changes.
- Verify all 11 artifacts can be loaded and produce finite, non-negative forecasts.
- Report evaluation metrics and the forecast protocol used to calculate them.

## Pull request checklist

- [ ] The change has a clear purpose and limited scope.
- [ ] Tests cover new or changed behavior.
- [ ] `python scripts/verify.py` passes locally.
- [ ] Documentation and examples are current.
- [ ] No secrets, caches, or unnecessary binaries were added.
- [ ] Backward compatibility was considered for API fields and model IDs.
