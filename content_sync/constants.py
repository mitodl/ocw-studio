"""Constants for content_sync"""
VERSION_LIVE = "live"
VERSION_DRAFT = "draft"
START_TAG_PREFIX = "# START "
END_TAG_PREFIX = "# END "
DEV_START = f"{START_TAG_PREFIX}DEV-ONLY"
DEV_END = f"{END_TAG_PREFIX}DEV-ONLY"
NON_DEV_START = f"{START_TAG_PREFIX}NON-DEV"
NON_DEV_END = f"{END_TAG_PREFIX}NON-DEV"
DEV_ENDPOINT_URL = "http://10.1.0.100:9000"
