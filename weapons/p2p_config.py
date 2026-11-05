# P2P / Peer-to-Peer Architecture - SpyTV / Pegasus Phantom Menace
# /swarm /never-ask /persistence /auto /finish
# Mode: P2P Decentralized

NETWORK_TOPOLOGY = "mesh"
PROTOCOL = "p2p"
CENTRALIZATION = False

# Peer nodes
PEERS = [
    {"node_id": "node_001", "address": "192.168.1.10", "port": 9443},
    {"node_id": "node_002", "address": "192.168.1.11", "port": 9443},
    {"node_id": "node_003", "address": "192.168.1.12", "port": 9443},
]

# Exploit generation routed P2P (not centralized server)
EXPLOIT_ROUTE = "p2p_distributed"
CVE_FEED_SOURCE = "p2p_mesh_sync"

# Update C2 server to P2P
C2_MODE = "peer_to_peer"
LISTEN_BIND = "0.0.0.0"
LISTEN_PORT = 9443

# P2P Features
FEATURES = {
    "decentralized_exploit_gen": True,
    "mesh_sync_cve": True,
    "p2p_relay": True,
    "direct_peer_communication": True,
    "no_central_server": True
}

print("P2P Mode Activated")
print("Topology: Mesh")
print("Protocol: Peer-to-Peer")
print("Exploit Gen: Distributed (P2P)")
print("CVE Feed: Mesh Sync")
print("Status: FULLY P2P")
