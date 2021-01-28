"""
Django app
"""
from mitol.common import envs
from mitol.common.apps import BaseApp


class RootConfig(BaseApp):
    """AppConfig for this project"""

    name = "main"

    def ready(self):
        envs.validate()
