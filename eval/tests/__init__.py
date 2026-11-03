"""Offline tests for the Evaluation Suite. Run from the repository root:

    python3 -m unittest discover -s eval/tests -t .
"""

import os

from eval import dataset


def dataset_fingerprint():
    """(SHA-256, mtime in ns) of the test set, to check that the tests never change it."""
    path = dataset.DEFAULT_DATASET
    return dataset.sha256_file(path), os.stat(path).st_mtime_ns


def test_set_guard():
    """A module's setUpModule and tearDownModule: the module must leave the test set unchanged."""
    before = []

    def set_up():
        before.append(dataset_fingerprint())

    def tear_down():
        assert dataset_fingerprint() == before[0], "the test set changed while the tests ran"

    return set_up, tear_down
