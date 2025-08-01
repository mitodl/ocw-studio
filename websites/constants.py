"""Constants for websites"""

from model_utils import Choices

CONTENT_TYPE_PAGE = "page"
CONTENT_TYPE_VIDEO_GALLERY = "video_gallery"
CONTENT_TYPE_RESOURCE = "resource"
CONTENT_TYPE_RESOURCE_COLLECTION = "resource_collections"
CONTENT_TYPE_RESOURCE_LIST = "resource-list"
CONTENT_TYPE_INSTRUCTOR = "instructor"
CONTENT_TYPE_METADATA = "sitemetadata"
CONTENT_TYPE_NAVMENU = "navmenu"
CONTENT_TYPE_COURSE_LIST = "course-lists"
CONTENT_TYPE_EXTERNAL_RESOURCE = "external-resource"
CONTENT_TYPE_WEBSITE = "website"

BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK = 100

COURSE_PAGE_LAYOUTS = ["instructor_insights"]
COURSE_RESOURCE_LAYOUTS = ["pdf", "video"]

CONTENT_FILENAME_MAX_LEN = 125
CONTENT_FILENAMES_FORBIDDEN = ("index", "_index")
CONTENT_DIRPATH_MAX_LEN = 300
CONTENT_FILEPATH_UNIQUE_CONSTRAINT = "unique_page_content_destination"

WEBSITE_SOURCE_STUDIO = "studio"
WEBSITE_SOURCE_OCW_IMPORT = "ocw-import"
WEBSITE_SOURCES = [WEBSITE_SOURCE_STUDIO, WEBSITE_SOURCE_OCW_IMPORT]

STARTER_SOURCE_GITHUB = "github"
STARTER_SOURCE_LOCAL = "local"
STARTER_SOURCES = [STARTER_SOURCE_GITHUB, STARTER_SOURCE_LOCAL]

WEBSITE_CONFIG_FILENAME = "ocw-studio.yml"
WEBSITE_CONFIG_CONTENT_DIR_KEY = "content-dir"
WEBSITE_CONFIG_DEFAULT_CONTENT_DIR = "content"
WEBSITE_CONFIG_ROOT_URL_PATH_KEY = "root-url-path"
WEBSITE_CONFIG_SITE_URL_FORMAT_KEY = "site-url-format"
WEBSITE_CONTENT_FILETYPE = "md"
CONTENT_MENU_FIELD = "menu"

OMNIBUS_STARTER_SLUG = "omnibus-starter"
OCW_WWW_STARTER_SLUG = "ocw-www"

GLOBAL_ADMIN = "global_admin"
GLOBAL_AUTHOR = "global_author"

ADMIN_GROUP_PREFIX = "admins_website_"
EDITOR_GROUP_PREFIX = "editors_website_"


PERMISSION_ADD = "websites.add_website"
PERMISSION_VIEW = "websites.view_website"
PERMISSION_PREVIEW = "websites.preview_website"
PERMISSION_EDIT = "websites.change_website"
PERMISSION_PUBLISH = "websites.publish_website"
PERMISSION_EDIT_CONTENT = "websites.edit_content_website"
PERMISSION_COLLABORATE = "websites.add_collaborators_website"

POSTHOG_ENABLE_EDITABLE_PAGE_URLS = "OCW_STUDIO_EDITABLE_PAGE_URLS"

ROLE_ADMINISTRATOR = "admin"
ROLE_EDITOR = "editor"
ROLE_GLOBAL = "global_admin"
ROLE_OWNER = "owner"

GROUP_ROLES = {ROLE_ADMINISTRATOR, ROLE_EDITOR}
ROLE_GROUP_MAPPING = {
    ROLE_ADMINISTRATOR: ADMIN_GROUP_PREFIX,
    ROLE_EDITOR: EDITOR_GROUP_PREFIX,
    ROLE_GLOBAL: GLOBAL_ADMIN,
}

PERMISSIONS_GLOBAL_AUTHOR = [PERMISSION_ADD]
PERMISSIONS_EDITOR = [PERMISSION_VIEW, PERMISSION_PREVIEW, PERMISSION_EDIT_CONTENT]
PERMISSIONS_ADMIN = [
    *PERMISSIONS_EDITOR,
    PERMISSION_PUBLISH,
    PERMISSION_COLLABORATE,
    PERMISSION_EDIT,
]


INSTRUCTORS_FIELD_NAME = "instructors"


EXTERNAL_IDENTIFIER_PREFIX = "external-"


RESOURCE_TYPE_VIDEO = "Video"
RESOURCE_TYPE_DOCUMENT = "Document"
RESOURCE_TYPE_IMAGE = "Image"
RESOURCE_TYPE_OTHER = "Other"

ADMIN_ONLY_CONTENT = ["sitemetadata"]

PUBLISH_STATUS_SUCCEEDED = "succeeded"
PUBLISH_STATUS_PENDING = "pending"
PUBLISH_STATUS_STARTED = "started"
PUBLISH_STATUS_ERRORED = "errored"
PUBLISH_STATUS_ABORTED = "aborted"
PUBLISH_STATUS_NOT_STARTED = "not-started"
PUBLISH_STATUSES = [
    PUBLISH_STATUS_SUCCEEDED,
    PUBLISH_STATUS_PENDING,
    PUBLISH_STATUS_STARTED,
    PUBLISH_STATUS_ERRORED,
    PUBLISH_STATUS_ABORTED,
    PUBLISH_STATUS_NOT_STARTED,
]
PUBLISH_STATUSES_FINAL = [
    PUBLISH_STATUS_SUCCEEDED,
    PUBLISH_STATUS_ERRORED,
    PUBLISH_STATUS_ABORTED,
]

OCW_HUGO_THEMES_GIT = "https://github.com/mitodl/ocw-hugo-themes.git"


class WebsiteStarterStatus:
    """Simple class for values/keys of status in website starter"""

    DEFAULT = "default"
    ACTIVE = "active"
    INACTIVE = "inactive"

    ALLOWED_STATUSES = [DEFAULT, ACTIVE]
    ALL_STATUSES = [DEFAULT, ACTIVE, INACTIVE]


WEBSITE_STARTER_STATUS_CHOICES = Choices(
    (WebsiteStarterStatus.DEFAULT, "Default"),
    (WebsiteStarterStatus.ACTIVE, "Active"),
    (WebsiteStarterStatus.INACTIVE, "Inactive"),
)

WEBSITE_CONTENT_LEFTNAV = "leftnav"
WEBSITE_PAGES_PATH = "pages"
