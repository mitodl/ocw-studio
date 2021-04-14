""" Syncing API """
from content_sync.models import ContentSyncState
from websites.models import WebsiteContent


def upsert_content_sync_state(content: WebsiteContent):
    """ Create the content sync state """
    ContentSyncState.objects.update_or_create(
        content=content, defaults=dict(current_checksum=content.calculate_checksum())
    )
