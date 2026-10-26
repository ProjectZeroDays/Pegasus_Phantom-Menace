import base64, zlib, re
with open('pegasus_v_1.4.py', 'r', encoding='utf-8') as f:
    content = f.read()
match = re.search(r'BLOB = "(.+?)"', content, re.DOTALL)
print('BLOB found:', bool(match))
if match:
    try:
        SECRET = b"secret!"
        def xor_bytes(data, key):
            return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        raw = base64.b64decode(match.group(1).encode())
        plain = zlib.decompress(xor_bytes(raw, SECRET))
        text = plain.decode('utf-8', errors='replace')
        print('BLOB decrypt OK, length:', len(text))
        print('Contains "Pegasus":', 'Pegasus' in text)
        print('Contains "ProjectZeroDays":', 'ProjectZeroDays' in text)
    except Exception as e:
        print('BLOB error:', e)
