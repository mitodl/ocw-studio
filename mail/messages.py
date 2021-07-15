"""Test email messages"""
from types import SimpleNamespace

from mitol.mail.messages import TemplatedMessage


class SampleMessage(TemplatedMessage):
    """Sample email message"""

    name = "Sample"
    template_name = "mail/sample"

    @staticmethod
    def get_debug_template_context():
        """Returns the extra context for the email debugger"""
        return {"user": SimpleNamespace(first_name="Sally")}
