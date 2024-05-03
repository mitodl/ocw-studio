"""Website email messages"""

from types import SimpleNamespace

from mitol.mail.messages import TemplatedMessage

from content_sync.constants import VERSION_LIVE


class VideoTranscriptingCompleteMessage(TemplatedMessage):
    """Email message for 3play transcription complete"""

    name = "3play transcription complete"
    template_name = "mail/transcription_complete"

    @staticmethod
    def get_debug_template_context() -> dict:
        """Returns the extra context for the email debugger"""  # noqa: D401
        return {
            "user": SimpleNamespace(name="Test User"),
            "site": SimpleNamespace(
                name="1-1-computer-science-fall-2024",
                title="Intro to Computer Science",
                full_url="https://ocwtest.edu/courses/1-1-computer-science-fall-2024",
            ),
        }


class PreviewOrPublishSuccessMessage(TemplatedMessage):
    """Email message for publish/preview pipeline success"""

    name = "Website Preview/Publish Pipeline Completed"
    template_name = "mail/preview_publish_success"

    @staticmethod
    def get_debug_template_context() -> dict:
        """Returns the extra context for the email debugger"""  # noqa: D401
        return {
            "user": SimpleNamespace(name="Test User"),
            "site": SimpleNamespace(
                name="1-1-computer-science-fall-2024",
                title="Intro to Computer Science",
                full_url="https://ocwtest.edu/courses/1-1-computer-science-fall-2024",
            ),
            "version": VERSION_LIVE,
        }


class PreviewOrPublishFailureMessage(TemplatedMessage):
    """Email message for publish/preview pipeline failure"""

    name = "Website Preview/Publish Pipeline Failed"
    template_name = "mail/preview_publish_failure"

    @staticmethod
    def get_debug_template_context() -> dict:
        """Returns the extra context for the email debugger"""  # noqa: D401
        return {
            "user": SimpleNamespace(name="Test User"),
            "site": SimpleNamespace(
                name="1-1-computer-science-fall-2024",
                title="Intro to Computer Science",
                full_url="https://ocwtest.edu/courses/1-1-computer-science-fall-2024",
            ),
            "version": VERSION_LIVE,
        }
