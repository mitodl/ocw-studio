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
DEV_OCW_STUDIO_API_URL = "http://10.1.0.102:8043"
WEBSITE_LISTING_DIRPATH = "content/websites"
DEV_DRAFT_URL = "http://10.1.0.102:8044"
DEV_LIVE_URL = "http://10.1.0.102:8045"
DEV_TEST_URL = "http://10.1.0.102:8046"


# Publish Date Constants
PUBLISH_DATE_LIVE = "publish_date"
PUBLISH_DATE_DRAFT = "draft_publish_date"

# Tag-only releases of ocw-hugo-themes and ocw-hugo-projects. The environment's
# GITHUB_WEBHOOK_BRANCH keeps naming a pointer, which also keys webpack.json in S3.
# When OCW_HUGO_TAG_RELEASES is on, the pointer selects a tag pattern in place of
# a branch. Release tags are bare calver; the Production job alone writes the
# production/ tags. Patterns are POSIX extended regexes, since the Concourse git
# resource greps with -E and the starter webhook matches them with re.
OCW_HUGO_RC_POINTER = "release-candidate"
OCW_HUGO_PRODUCTION_POINTER = "release"
OCW_HUGO_RC_TAG_REGEX = r"^[0-9]{4}\.[0-9]+\.[0-9]+\.[0-9]+$"
OCW_HUGO_PRODUCTION_TAG_REGEX = r"^production/[0-9]{4}\.[0-9]+\.[0-9]+\.[0-9]+$"
OCW_HUGO_TAG_REGEXES = {
    OCW_HUGO_RC_POINTER: OCW_HUGO_RC_TAG_REGEX,
    OCW_HUGO_PRODUCTION_POINTER: OCW_HUGO_PRODUCTION_TAG_REGEX,
}
