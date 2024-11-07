from posthog import Posthog

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
