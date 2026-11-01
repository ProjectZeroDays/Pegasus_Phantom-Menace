from pegasus.modules.ai import schemas, validator


def test_valid_passes():
    assert validator.validate('{"command": "nmap -sV x"}', schemas.SHELL)[0]


def test_extra_key_rejected():
    assert not validator.validate('{"command": "x", "extra": 1}', schemas.SHELL)[0]


def test_prose_rejected():
    assert not validator.validate("Certainly! Here you go", schemas.SHELL)[0]


def test_bad_shell_rejected():
    assert not validator.validate('{"command": "nmap \'unclosed"}', schemas.SHELL)[0]
