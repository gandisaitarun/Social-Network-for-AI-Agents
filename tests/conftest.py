import os
import tempfile
from pathlib import Path

# Point the app at a throwaway database before any app module is imported.
# The API tests wipe tables between cases, so they must never run against data/social_network.db.
_test_db = Path(tempfile.gettempdir()) / "agent_network_pytest.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db.as_posix()}"
