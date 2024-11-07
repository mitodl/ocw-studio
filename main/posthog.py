from posthog import Posthog

from main.settings import ENVIRONMENT, POSTHOG_API_HOST, POSTHOG_PROJECT_API_KEY

posthog = Posthog(POSTHOG_PROJECT_API_KEY, host=POSTHOG_API_HOST)

if ENVIRONMENT == "dev":
    posthog.debug = True
