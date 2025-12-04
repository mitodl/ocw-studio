"""Feature flag constants for OCW Studio backend."""

# PostHog Feature Flags

# Controls whether YouTube video metadata updates are disabled.
# When enabled, disables automatic YouTube metadata updates during publish.
# This can be used to prevent unwanted notifications to YouTube subscribers
# during bulk publishing or testing.
FEATURE_FLAG_DISABLE_YOUTUBE_UPDATE = "OCW_STUDIO_DISABLE_YOUTUBE_UPDATE"

# Controls whether content deletion should check for references.
# When enabled, prevents deletion of content that is referenced elsewhere
# in the website to maintain data integrity.
FEATURE_FLAG_CONTENT_DELETABLE_REFERENCES = "OCW_STUDIO_CONTENT_DELETABLE_REFERENCES"
