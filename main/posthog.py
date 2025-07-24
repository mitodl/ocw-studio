"""PostHog integration for feature flags and analytics."""

from posthog import Posthog

from main.settings import (
    ENVIRONMENT,
    POSTHOG_API_HOST,
    POSTHOG_ENABLED,
    POSTHOG_PROJECT_API_KEY,
)

posthog = None
if POSTHOG_ENABLED:
    posthog = Posthog(POSTHOG_PROJECT_API_KEY, host=POSTHOG_API_HOST)

    if posthog and ENVIRONMENT == "dev":
        posthog.debug = True


def is_feature_enabled(feature_key, distinct_id=ENVIRONMENT):
    """Check whether feature flag is enabled"""
    if not POSTHOG_ENABLED or posthog is None:
        return False

    # Handle None distinct_id which is not allowed in PostHog 4.x
    if distinct_id is None:
        distinct_id = ENVIRONMENT

    return posthog.feature_enabled(
        feature_key, distinct_id, person_properties={"environment": ENVIRONMENT}
    )
