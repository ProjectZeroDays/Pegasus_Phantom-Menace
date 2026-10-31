import sqlite3
conn = sqlite3.connect('pcap_engine/journal.db')
with open('pcap_engine/journal.schema.sql') as f:
    conn.executescript(f.read())
conn.commit()
print('journal.db created')
print('Tables:', conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())
