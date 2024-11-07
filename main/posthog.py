from posthog import Posthog, feature_enabled

from main.settings import (
    ENVIRONMENT,
    POSTHOG_API_HOST,
    POSTHOG_ENABLED,
    POSTHOG_PROJECT_API_KEY,
)

if POSTHOG_ENABLED:
    posthog = Posthog(POSTHOG_PROJECT_API_KEY, host=POSTHOG_API_HOST)

    if ENVIRONMENT == "dev":
        posthog.debug = True


def is_feature_enable(feature_key, user_id):
    """Check for Feature flag"""
    return POSTHOG_ENABLED and feature_enabled(feature_key, user_id)
