# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in jobsearch-pipeline, please
report it responsibly using **GitHub Private Security Advisories**:

1. Go to https://github.com/socraticblock/jobsearch-pipeline/security/advisories
2. Click "New draft security advisory"
3. Fill in the details and submit

**Do not** open a public issue or pull request for security vulnerabilities.

We will acknowledge receipt within 72 hours and provide a timeline for
resolution.

## Scope

The following are in scope for security reports:

- Credential leakage in published artifacts
- Path traversal or injection in data ingestion
- Unauthorized data access in the local ledger
- Supply-chain issues in dependencies

## Out of Scope

- Vulnerabilities in third-party dependencies (report upstream)
- Issues requiring physical access to the host machine
- Social engineering attacks

## Security Model

jobsearch-pipeline is a **local-first** tool. It stores all data in a local
SQLite database (`~/.local/share/jobsearch/jobs.db`) and does not transmit
personal data to external services. Network access is limited to:

- Fetching job postings from public job-board APIs (RemoteOK, Remotive, etc.)
- Optional email ingestion (user-configured, read-only)

No telemetry, analytics, or tracking is collected.

## Disclosure Policy

We follow coordinated disclosure. Vulnerabilities will be patched and
disclosed after a fix is available, with credit to the reporter unless
they prefer anonymity.