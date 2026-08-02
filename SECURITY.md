# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `0.x` (main) | Yes |
| Unreleased local builds | Best effort |

## Reporting a vulnerability

Please **do not** open a public issue for security-sensitive reports.

1. Use GitHub **Private vulnerability reporting** (Security → Advisories → Report a vulnerability), or
2. Email the maintainer listed in `CITATION.cff` / repository profile once published.

Include:

- Affected component (`adventure-cli`, pack builder, inference, etc.)
- Reproduction steps
- Impact assessment (RCE, path traversal, model prompt injection with local impact, etc.)

We aim to acknowledge reports within **7 days** and provide a remediation plan when confirmed.

## What is not a vulnerability

- Incorrect mission rankings or preference-vector scores
- Incomplete OSM / DEM coverage in a Region Pack
- LLM intent misinterpretation (product quality, not security)
- Missing tourist attractions

Pack GeoJSON and DEM tiles are local data products; treat untrusted pack files like any untrusted input if you load third-party packs.
