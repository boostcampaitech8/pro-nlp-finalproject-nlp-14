"""Application constants and configuration values"""

# File upload limits
MAX_RECORDING_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# URL expiration
PRESIGNED_URL_EXPIRATION = 3600  # 1 hour in seconds

# Recording formats
SUPPORTED_RECORDING_FORMATS = ["webm", "mp4", "mkv"]
DEFAULT_RECORDING_FORMAT = "webm"
