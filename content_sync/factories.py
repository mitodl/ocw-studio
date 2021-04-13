""" Content sync factories """
from factory import SubFactory
from factory.django import DjangoModelFactory


class ContentSyncStateFactory(DjangoModelFactory):
    """ Factory for ContentSyncState """

    content = SubFactory("websites.factories.WebsiteContentFactory")

    class Meta:
        model = "content_sync.ContentSyncState"
        django_get_or_create = ("content",)
