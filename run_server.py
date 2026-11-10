import sys
sys.path.insert(0, r"C:\Projects\Pegasus_Phantom-Menace")
from pegasus.ui.web.backend.app import create_app
app = create_app()
app.run(host="0.0.0.0", port=5000)
