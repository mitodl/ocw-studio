"""Website email messages"""
from types import SimpleNamespace

from mitol.mail.messages import TemplatedMessage


class PreviewOrPublishSuccessMessage(TemplatedMessage):
    """Email message for publish/preview pipeline success"""

    name = "Website Preview/Publish Pipeline Completed"
    template_name = "mail/preview_publish_success"

    @staticmethod
    def get_debug_template_context() -> dict:
        """Returns the extra context for the email debugger"""
        return {
            "site": SimpleNamespace(
                name="1-1-computer-science-fall-2024",
                title="Intro to Computer Science",
                full_url="https://ocwtest.edu/courses/1-1-computer-science-fall-2024",
            ),
            "version": "live",
        }
