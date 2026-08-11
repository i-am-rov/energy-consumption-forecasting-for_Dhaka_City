# Security Policy

## Supported version

Security fixes are applied to the latest version on the `main` branch.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's **Security** tab by opening a private vulnerability report. Do not disclose exploitable details in a public issue.

Include, when possible:

- A concise description of the vulnerability and its impact
- Reproduction steps or a minimal proof of concept
- Affected endpoints, files, dependencies, or deployment configurations
- Suggested mitigations or fixes

An initial acknowledgement should be provided within five business days. Confirmed issues will be prioritized according to their impact and exploitability.

## Project-specific risks

- Treat joblib and pickle-compatible model artifacts as executable code. Load artifacts only from trusted sources.
- Never commit API keys, tokens, cloud credentials, or private datasets.
- Validate dependency upgrades with the complete verification suite.
- Keep the API behind appropriate authentication and network controls when forecasts or operational data are sensitive.
- Review model and data changes for poisoning, schema drift, target leakage, and unexpectedly large forecast deviations.

## Public discussions

After a fix is available, non-sensitive remediation details may be documented in a GitHub issue, release note, or advisory.
