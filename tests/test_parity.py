from pegasus.modules.parity import matrix


def test_counts_derived():
    report = matrix.report()
    assert report["domains"]["delivery"]["done"] == matrix._count_vectors()
    assert report["domains"]["delivery"]["done"] == 13


def test_never_exceeds_target():
    for domain in matrix.report()["domains"].values():
        assert domain["done"] <= domain["target"]
