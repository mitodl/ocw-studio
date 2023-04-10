"""Constants for content_sync"""
VERSION_LIVE = "live"
VERSION_DRAFT = "draft"
TARGET_ONLINE = "online"
TARGET_OFFLINE = "offline"
START_TAG_PREFIX = "# START "
END_TAG_PREFIX = "# END "
DEV_START = f"{START_TAG_PREFIX}DEV-ONLY"
DEV_END = f"{END_TAG_PREFIX}DEV-ONLY"
NON_DEV_START = f"{START_TAG_PREFIX}NON-DEV"
NON_DEV_END = f"{END_TAG_PREFIX}NON-DEV"
ONLINE_START = f"{START_TAG_PREFIX}ONLINE-ONLY"
ONLINE_END = f"{END_TAG_PREFIX}ONLINE-ONLY"
OFFLINE_START = f"{START_TAG_PREFIX}OFFLINE-ONLY"
OFFLINE_END = f"{END_TAG_PREFIX}OFFLINE-ONLY"
DEV_ENDPOINT_URL = "http://10.1.0.100:9000"
WEBSITE_LISTING_DIRPATH = "content/websites"
LEGACY_VIDEO_IMPORT_S3_BUCKET = "ocw-website-mirror"
LEGACY_VIDEO_IMPORT_S3_PATH = "OcwExport/InternetArchive/"
