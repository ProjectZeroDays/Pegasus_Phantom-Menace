from pegasus.modules.parity import matrix


def test_counts_derived():
    from pegasus.modules.delivery import adapters, legacy

    report = matrix.report()
    assert report["domains"]["delivery"]["done"] == matrix._count_vectors()
    assert report["domains"]["delivery"]["done"] == len(adapters.REGISTRY) + len(legacy.LEGACY)
    assert report["domains"]["delivery"]["done"] > 0


def test_never_exceeds_target():
    for domain in matrix.report()["domains"].values():
        assert domain["done"] <= domain["target"]
        assert 0 <= domain["pct"] <= 100
