import re, base64, zlib, sys

ACTION = sys.argv[1]  # 'decrypt' or 'encrypt'

def xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

SECRET = b"secret!"

if ACTION == "decrypt":
    src = open("pegasus_v_1.4.py", encoding="utf-8").read()
    blob = re.search(r'BLOB = "(.+?)"', src, re.S).group(1)
    code = zlib.decompress(xor_bytes(base64.b64decode(blob), SECRET)).decode("utf-8")
    open("payload_src_1.3.py", "w", encoding="utf-8", newline="\n").write(code)
    print("decrypted ->", len(code), "chars")
else:
    code = open("payload_src_1.3.py", encoding="utf-8").read()
    blob = base64.b64encode(xor_bytes(zlib.compress(code.encode("utf-8")), SECRET)).decode()
    src = open("pegasus_v_1.4.py", encoding="utf-8").read()
    new_src, n = re.subn(r'BLOB = ".+?"', 'BLOB = "%s"' % blob, src, count=1, flags=re.S)
    assert n == 1, "BLOB not found"
    open("pegasus_v_1.4.py", "w", encoding="utf-8", newline="\r\n").write(new_src)
    print("encrypted payload ->", len(blob), "chars of BLOB")
