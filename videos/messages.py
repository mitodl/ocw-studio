"""message classes for videos"""

from types import SimpleNamespace

from mitol.mail.messages import TemplatedMessage


class YouTubeUploadSuccessMessage(TemplatedMessage):
    """Email message for Youtube upload success"""

    name = "YouTube Video Upload Completed"
    template_name = "mail/youtube_upload_success"

    @staticmethod
    def get_debug_template_context() -> dict:
        """Returns the extra context for the email debugger"""  # noqa: D401
        return {
            "user": SimpleNamespace(name="Test User"),
            "site": SimpleNamespace(
                title="Intro to Computer Science",
                url="https://ocwtest.edu/courses/1-1-computer-science-fall-2024",
            ),
            "video": SimpleNamespace(
                filename="course_video_1.mp4", url="https://youtu.be/yMiTVid12"
            ),
        }


class YouTubeUploadFailureMessage(TemplatedMessage):
    """Email message for Youtube upload failure"""

    name = "YouTube Video Upload Failed"
    template_name = "mail/youtube_upload_failure"

    @staticmethod
    def get_debug_template_context() -> dict:
        """Returns the extra context for the email debugger"""  # noqa: D401
        return {
            "user": SimpleNamespace(name="Test User"),
            "site": SimpleNamespace(
                title="Intro to Computer Science",
                url="https://ocwtest.edu/courses/1-1-computer-science-fall-2024",
            ),
            "video": SimpleNamespace(filename="course_video_1.mp4"),
        }
