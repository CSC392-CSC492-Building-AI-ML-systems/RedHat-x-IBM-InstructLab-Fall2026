"""Offline tests for the Evaluation Suite. Run from the repository root:

    python3 -m unittest discover -s eval/tests -t .
"""

import os

from eval import dataset


def dataset_fingerprint():
    """(SHA-256, mtime in ns) of each test set (the group defaults and the pinned files: Group B v4 and
    v3, Group A), to check that the tests never change them."""
    paths = list(dict.fromkeys([g.default_path for g in dataset.GROUPS.values()] + list(dataset.PINNED_SHA256)))
    return [(dataset.sha256_file(p), os.stat(p).st_mtime_ns) for p in paths]


def test_set_guard():
    """A module's setUpModule and tearDownModule: the module must leave the test set unchanged."""
    before = []

    def set_up():
        before.append(dataset_fingerprint())

    def tear_down():
        assert dataset_fingerprint() == before[0], "the test set changed while the tests ran"

    return set_up, tear_down
