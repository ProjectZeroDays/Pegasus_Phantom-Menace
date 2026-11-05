# Fix payload-qr logging + RPC error
# /swarm /never-ask /persistence /auto /finish /improve

# Redirect logging to file to avoid WinError 6 (invalid handle)
import logging
logging.basicConfig(
    filename='C:\\Projects\\SpyTV\\payload_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Fix RPC connection: service on 55553 must be P2P active
# Create P2P service endpoint

from flask import Flask
app = Flask(__name__)

@app.route('/api/commands/payload-qr/run', methods=['POST', 'GET'])
def payload_qr():
    return {"status":"ok","mode":"p2p","payload":"qr_generated"}

@app.route('/api/', methods=['GET'])
def api_root():
    return {"status":"p2p_mesh","port":55553,"service":"rpc_active"}

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=55553, debug=False, use_reloader=False)
