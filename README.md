# OS3 Focus Stacking

A web interface that processes focus stacks produced by
[OpenScan3](https://github.com/OpenScan-org/OpenScan3), running live while a
scan is in progress, with the existing OS3 web UI embedded alongside it.

## Relation to OpenScan3 / OpenScan3-Client

OpenScan3 ships two separate repos: `OpenScan3` (Python/FastAPI firmware,
runs on the Pi) and `OpenScan3-Client` (Vue.js SPA, the web UI). This project
extends `OpenScan3-Client` with an additional "Stacking" tab, next to its
existing "Scan" tab — an additive change built and shipped as part of the
same Vue application, not a fork or an embedded iframe. The goal is for it to
be mergeable upstream as a pull request. The `OpenScan3` firmware itself is
not modified.

The page is served by the Pi like the rest of the client. Computation
(aligning and merging focus stacks) runs in the browser by default, with an
optional local helper program for larger scans planned for later (see the
roadmap).

## Status

Step 0 done: the compute interface is specified in
[docs/spec/](docs/spec/compute-interface.md); nothing runs yet. See
[ROADMAP.md](ROADMAP.md) for the full plan, architecture decisions, and
current step. [AGENTS.md](AGENTS.md) has a short reference for anyone (human
or agent) implementing a step, including the repository layout and the
upstream change check (`python tools/check_upstream.py`).

## License

GPL-3.0, consistent with `OpenScan3` and `OpenScan3-Client`. See
[LICENSE](LICENSE).
