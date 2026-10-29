"""Pytest collection config.

The ``test/end2end/`` suite is ovoscope-driven and needs the heavy e2e stack
(``ovoscope``, ``ovos-core`` and ``ovos-m2v-pipeline``, the ``end2end`` extra).
It is exercised by the dedicated ``ovoscope`` CI job. The lightweight
``build_tests``/``coverage`` jobs install only the ``test`` extra and would
error importing the end2end modules, so skip collecting them when ovoscope is
not installed.
"""
from importlib.util import find_spec

collect_ignore_glob = []

if find_spec("ovoscope") is None:
    collect_ignore_glob.append("end2end/*")
