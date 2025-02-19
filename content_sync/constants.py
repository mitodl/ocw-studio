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
DEV_DRAFT_URL = "http://10.1.0.102:8044"
DEV_LIVE_URL = "http://10.1.0.102:8045"
DEV_TEST_URL = "http://10.1.0.102:8046"


# Publish Date Constants
PUBLISH_DATE_LIVE = "publish_date"
PUBLISH_DATE_DRAFT = "draft_publish_date"
