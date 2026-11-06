import os
import tempfile

# Settings are read once and cached, so point uploads at a throwaway folder before any app
# module is imported.
os.environ.setdefault("FLAKERADAR_UPLOAD_DIR", tempfile.mkdtemp(prefix="flakeradar-uploads-"))
os.environ.setdefault("FLAKERADAR_LOG_LEVEL", "WARNING")

# Integration tests need PostgreSQL and Redis; skip collecting them when not configured.
collect_ignore_glob = [] if "FLAKERADAR_DATABASE_URL" in os.environ else ["integration/*"]
