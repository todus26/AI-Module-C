import os
import tempfile

os.environ["PANTRY_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "pantry.db")
