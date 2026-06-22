"""Feature flag constants for OCW Studio backend."""

# PostHog Feature Flags

# Controls whether YouTube video metadata updates are enabled.
# YouTube updates are blocked by default. When this flag is True,
# automatic YouTube metadata updates are enabled during publish.
# Test videos in YT_TEST_VIDEO_IDS always bypass this flag.
FEATURE_FLAG_ENABLE_YOUTUBE_UPDATE = "OCW_STUDIO_ENABLE_YOUTUBE_UPDATE"

# Controls whether content deletion should check for references.
# When enabled, prevents deletion of content that is referenced elsewhere
# in the website to maintain data integrity.
FEATURE_FLAG_CONTENT_DELETABLE_REFERENCES = "OCW_STUDIO_CONTENT_DELETABLE_REFERENCES"
