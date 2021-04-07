""" Constants for websites """

CONTENT_TYPE_PAGE = "page"
CONTENT_TYPE_RESOURCE = "resource"

COURSE_HOME = "course-home"
COURSE_PAGE_LAYOUTS = ["course_home", "course_section", "instructor_insights"]
COURSE_RESOURCE_LAYOUTS = ["pdf", "video"]

WEBSITE_SOURCE_STUDIO = "studio"
WEBSITE_SOURCE_OCW_IMPORT = "ocw-import"
WEBSITE_SOURCES = [WEBSITE_SOURCE_STUDIO, WEBSITE_SOURCE_OCW_IMPORT]

STARTER_SOURCE_GITHUB = "github"
STARTER_SOURCE_LOCAL = "local"
STARTER_SOURCES = [STARTER_SOURCE_GITHUB, STARTER_SOURCE_LOCAL]

COURSE_STARTER_SLUG = "course"

WEBSITE_CONFIG_FILENAME = "ocw-studio.yml"


GLOBAL_ADMIN = "global_admin"
GLOBAL_AUTHOR = "global_author"

ADMIN_GROUP = "admins_website_"
EDITOR_GROUP = "editors_website_"

PERMISSION_ADD = "websites.add_website"
PERMISSION_VIEW = "websites.view_website"
PERMISSION_PREVIEW = "websites.preview_website"
PERMISSION_EDIT = "websites.change_website"
PERMISSION_PUBLISH = "websites.publish_website"
PERMISSION_EDIT_CONTENT = "websites.edit_content_website"
PERMISSION_COLLABORATE = "websites.add_collaborators_website"

ROLE_ADMINISTRATOR = "admin"
ROLE_EDITOR = "editor"
ROLE_GLOBAL = "global_admin"
ROLE_OWNER = "owner"

ROLE_GROUP_MAPPING = {ROLE_ADMINISTRATOR: ADMIN_GROUP, ROLE_EDITOR: EDITOR_GROUP}

PERMISSIONS_GLOBAL_AUTHOR = [PERMISSION_ADD]
PERMISSIONS_EDITOR = [PERMISSION_VIEW, PERMISSION_PREVIEW, PERMISSION_EDIT_CONTENT]
PERMISSIONS_ADMIN = PERMISSIONS_EDITOR + [
    PERMISSION_PUBLISH,
    PERMISSION_COLLABORATE,
    PERMISSION_EDIT,
]
