import json

import pytest

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.resources import (
    FASTLY_PURPOSE_LEARN,
    FASTLY_PURPOSE_TEST,
    fastly_resources,
    get_fastly_service_id,
)


@pytest.mark.parametrize(
    ("purpose", "service_id"),
    [
        (VERSION_DRAFT, "((fastly_draft.service_id))"),
        (VERSION_LIVE, "((fastly_live.service_id))"),
        (FASTLY_PURPOSE_LEARN, "((fastly_learn.service_id))"),
        (FASTLY_PURPOSE_TEST, "((fastly_test.service_id))"),
        ("unknown", None),
    ],
)
def test_get_fastly_service_id(purpose, service_id):
    """The Fastly service ID should match the Concourse variable for the purpose."""
    assert get_fastly_service_id(purpose) == service_id


@pytest.mark.parametrize(
    ("purpose", "service_ids"),
    [
        (VERSION_DRAFT, ["((fastly_draft.service_id))"]),
        (
            VERSION_LIVE,
            ["((fastly_live.service_id))", "((fastly_learn.service_id))"],
        ),
        (FASTLY_PURPOSE_TEST, ["((fastly_test.service_id))"]),
    ],
)
def test_fastly_resources_use_service_ids(settings, purpose, service_ids):
    """Fastly purge resources should target service IDs instead of domains."""
    resources = [
        json.loads(resource.model_dump_json(exclude_none=True))
        for resource in fastly_resources(purpose)
    ]

    assert [resource["source"]["service_id"] for resource in resources] == service_ids
    assert all("domain" not in resource["source"] for resource in resources)
    assert all(resource["check_every"] == "never" for resource in resources)
    assert all(
        resource["source"]["api_token"] == settings.CONCOURSE_FASTLY_API_TOKEN_VAR
        for resource in resources
    )
