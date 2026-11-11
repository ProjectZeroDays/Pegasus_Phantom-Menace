import pathlib
import sys

# The package sits next to this launcher - never hardcode a build machine
# path, because the packaged desktop app runs from the user's own directory.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from pegasus.ui.web.backend.app import create_app  # noqa: E402

app = create_app()
app.run(host="0.0.0.0", port=5000)
