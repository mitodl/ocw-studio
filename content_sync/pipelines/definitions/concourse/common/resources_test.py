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
    ("purpose", "service_ids", "domains"),
    [
        (
            VERSION_DRAFT,
            ["((fastly_draft.service_id))"],
            ["draft.ocw.mit.edu"],
        ),
        (
            VERSION_LIVE,
            ["((fastly_live.service_id))", "((fastly_learn.service_id))"],
            ["live.ocw.mit.edu", "learn-test.mit.edu"],
        ),
        (
            FASTLY_PURPOSE_TEST,
            ["((fastly_test.service_id))"],
            ["test.ocw.mit.edu"],
        ),
    ],
)
def test_fastly_resources_use_service_ids_and_domains(
    settings, purpose, service_ids, domains
):
    """Fastly purge resources should include service IDs and domains."""
    resources = [
        json.loads(resource.model_dump_json(exclude_none=True))
        for resource in fastly_resources(purpose)
    ]

    assert [resource["source"]["service_id"] for resource in resources] == service_ids
    assert [resource["source"]["domain"] for resource in resources] == domains
    assert all(resource["check_every"] == "never" for resource in resources)
    assert all(
        resource["source"]["api_token"] == settings.CONCOURSE_FASTLY_API_TOKEN_VAR
        for resource in resources
    )
