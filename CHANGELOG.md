# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Compute interface specification (interface version 1): normative document,
  TypeScript types and helper HTTP API in `docs/spec/`.
- `tools/check_upstream.py` with `tools/upstream-baseline.json` to report
  upstream OpenScan3 / OpenScan3-Client changes to the files the spec depends on.
- `python/`: `os3stack` reference implementation (Step 1): OS3 v0.13.0's
  calibration and merging ported 1:1, batch discovery, calibration record
  output, CLI `os3stack stack <scan-dir>`, unit tests on synthetic images.
