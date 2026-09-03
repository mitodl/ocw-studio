"""
Tests for the backfill_mit_learn_topics management command.

The command reads each site's OCW ``topics`` metadata, resolves it through a
copy of MIT Learn's ``topics.yaml``, and writes the result into
``metadata["mit_learn_topics"]`` as ``[topic, subtopic]`` paths.

Learn's real topics.yaml is not checked in here, so these tests build a small
one out of shapes taken from it: a root mapped by an OCW name of its own
("Science & Math" <- "Science"), roots that Learn maps only for another offeror
and which are therefore reachable only by pass-through ("Engineering",
"Humanities"), and an OCW name claimed by two Learn topics under two different
roots ("Climate" <- "Earth Science" and "Climate Science").

The command tests drive the real command through ``call_command`` against
factory-built sites, matching the repo convention.
"""  # noqa: INP001

import csv
import re
from io import StringIO
from types import SimpleNamespace

import pytest
import yaml
from django.core.management import call_command

from content_sync.models import ContentSyncState
from websites.constants import CONTENT_TYPE_METADATA, CONTENT_TYPE_PAGE
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.management.commands.backfill_mit_learn_topics import (
    INVALID_PATHS,
    NOTHING_MAPPED,
    SKIPPED_CURATED,
    SKIPPED_NO_FIELD,
    SKIPPED_NO_TOPICS,
    UNCHANGED,
    UPDATED,
    TopicTaxonomy,
    learn_topic_options,
)
from websites.models import Website

pytestmark = pytest.mark.django_db

SCIENCE_ID = "11111111-1111-1111-1111-111111111111"
PHYSICS_ID = "11111111-1111-1111-1111-000000000002"
ENERGY_ID = "22222222-2222-2222-2222-222222222222"
ENGINEERING_ID = "33333333-3333-3333-3333-333333333333"
HUMANITIES_ID = "44444444-4444-4444-4444-444444444444"

# A marker for "let the helper build a starter", so that `starter=None` can keep
# its literal meaning of a site with no starter at all.
UNSET = object()


def topic_node(name, node_id, *, mappings=None, children=(), parent=None):
    """Build one topics.yaml node, shaped like the nodes in Learn's own file."""
    node = {
        "id": node_id,
        "name": name,
        "mappings": dict(mappings or {}),
        "children": list(children),
    }
    if parent:
        node["parent"] = parent
    return node


TAXONOMY_TOPICS = [
    topic_node(
        "Science & Math",
        SCIENCE_ID,
        mappings={"mitx": ["Science"], "ocw": ["Science"]},
        children=[
            topic_node(
                "Earth Science",
                "11111111-1111-1111-1111-000000000001",
                mappings={
                    "mitx": ["Environmental Studies"],
                    "ocw": ["Climate", "Earth Science", "Geology"],
                },
            ),
            topic_node(
                "Physics",
                PHYSICS_ID,
                mappings={"ocw": ["Physics", "Quantum Mechanics"]},
            ),
        ],
    ),
    topic_node(
        "Energy, Climate & Sustainability",
        ENERGY_ID,
        children=[
            topic_node(
                "Climate Science",
                "22222222-2222-2222-2222-000000000001",
                mappings={"ocw": ["Climate", "Sustainability"]},
            )
        ],
    ),
    topic_node(
        "Engineering",
        ENGINEERING_ID,
        mappings={"mitx": ["Engineering"]},
        children=[
            topic_node(
                "Computer Science",
                "33333333-3333-3333-3333-000000000001",
                mappings={
                    "ocw": ["Computer Science", "Software Design and Engineering"]
                },
            )
        ],
    ),
    topic_node("Humanities", HUMANITIES_ID, mappings={"mitx": ["Humanities"]}),
]

# What a starter's mit_learn_topics field offers: every path the taxonomy above
# can produce, so tests opt into the options check by narrowing this.
LEARN_OPTIONS_MAP = {
    "Science & Math": {"Earth Science": [], "Physics": []},
    "Energy, Climate & Sustainability": {"Climate Science": []},
    "Engineering": {"Computer Science": []},
    "Humanities": {},
}

OCW_TOPICS_FIELD_CONFIG = {
    "label": "Topics",
    "name": "topics",
    "widget": "hierarchical-select",
    "levels": [
        {"label": "Topic", "name": "topic"},
        {"label": "Subtopic", "name": "subtopic"},
        {"label": "Speciality", "name": "speciality"},
    ],
    "options_map": {"Science": {"Physics": ["Quantum Mechanics"]}},
}


def learn_topics_field(options_map):
    """Build the mit_learn_topics field a starter's config may define."""
    return {
        "label": "MIT Learn Topics",
        "name": "mit_learn_topics",
        "widget": "hierarchical-select",
        "levels": [
            {"label": "Topic", "name": "topic"},
            {"label": "Subtopic", "name": "subtopic"},
        ],
        "options_map": options_map,
    }


def site_config(*fields):
    """Build a minimal site config whose sitemetadata item carries `fields`."""
    return {
        "content-dir": "content",
        "collections": [
            {
                "name": "metadata",
                "label": "Metadata",
                "category": "Settings",
                "files": [
                    {
                        "file": "data/metadata.json",
                        "name": "sitemetadata",
                        "label": "Site Metadata",
                        "fields": [OCW_TOPICS_FIELD_CONFIG, *fields],
                    }
                ],
            }
        ],
    }


def make_starter(options_map=LEARN_OPTIONS_MAP, **kwargs):
    """Create a starter offering `options_map`; None omits the field entirely."""
    fields = [] if options_map is None else [learn_topics_field(options_map)]
    return WebsiteStarterFactory.create(config=site_config(*fields), **kwargs)


def make_site(*, topics=None, learn_topics=None, starter=UNSET, name=None):
    """
    Create a site and its sitemetadata content, and return the content.

    `topics` and `learn_topics` are written into the metadata only when given,
    so a site can be built with the keys genuinely absent. Creating content
    dirties the site's republish flags, so they are cleared here -- the tests
    need to see what the command itself changes.
    """
    website = WebsiteFactory.create(
        starter=make_starter() if starter is UNSET else starter,
        **({"name": name, "short_id": name} if name else {}),
    )
    metadata = {"course_title": website.title}
    if topics is not None:
        metadata["topics"] = topics
    if learn_topics is not None:
        metadata["mit_learn_topics"] = learn_topics
    content = WebsiteContentFactory.create(
        website=website, type=CONTENT_TYPE_METADATA, metadata=metadata
    )
    Website.objects.filter(pk=website.pk).update(
        has_unpublished_draft=False, has_unpublished_live=False
    )
    return content


def write_topics_yaml(tmp_path, topics, filename="topics.yaml"):
    """Write `topics` out as a topics.yaml file and return its path."""
    path = tmp_path / filename
    path.write_text(yaml.safe_dump({"topics": topics}))
    return str(path)


SUMMARY_LINE = re.compile(r"^\s+(\d+)\s\s(\S.*)$")


def summary_counts(output):
    """Parse the `  <count>  <outcome>` lines of the command's run summary."""
    return {
        match.group(2): int(match.group(1))
        for match in (SUMMARY_LINE.match(line) for line in output.splitlines())
        if match
    }


def run_command(topics_yaml, **kwargs):
    """Run the command, returning its output plus the parsed outcome counts."""
    out, err = StringIO(), StringIO()
    call_command(
        "backfill_mit_learn_topics", topics_yaml, stdout=out, stderr=err, **kwargs
    )
    output = out.getvalue()
    return SimpleNamespace(
        out=output, err=err.getvalue(), outcomes=summary_counts(output)
    )


def website_flags(website):
    """Read the site's (draft, live) unpublished-changes flags back from the db."""
    website = Website.objects.get(pk=website.pk)
    return website.has_unpublished_draft, website.has_unpublished_live


def sync_checksum(content):
    """Read the content's stored ContentSyncState checksum back from the db."""
    return ContentSyncState.objects.get(content=content).current_checksum


@pytest.fixture
def topics_yaml(tmp_path):
    """Write the fixture taxonomy out as a topics.yaml and return its path."""
    return write_topics_yaml(tmp_path, TAXONOMY_TOPICS)


@pytest.fixture
def taxonomy(topics_yaml):
    """Parse the fixture taxonomy."""
    return TopicTaxonomy.from_yaml(topics_yaml)


# ---------------------------------------------------------------------------
# TopicTaxonomy: parsing topics.yaml and resolving OCW names through it
# ---------------------------------------------------------------------------


def test_map_terms_fans_out_and_adds_ancestors(taxonomy):
    """An OCW name two Learn topics claim resolves to both, plus their ancestors."""
    assert taxonomy.map_terms(["Climate"]) == [
        "Climate Science",
        "Earth Science",
        "Energy, Climate & Sustainability",
        "Science & Math",
    ]


def test_map_terms_passes_through_learn_topic_names(taxonomy):
    """
    A term that is itself a Learn topic resolves without a mapping row.

    Learn maps "Engineering" only for mitx, so the OCW topic of the same name
    survives only via the pass-through branch.
    """
    assert taxonomy.map_terms(["Engineering"]) == ["Engineering"]


def test_map_terms_ignores_other_offerors_mappings(taxonomy):
    """A name mapped only under another offeror is not an OCW mapping."""
    assert taxonomy.map_terms(["Environmental Studies"]) == []


def test_map_terms_drops_unmappable_terms(taxonomy):
    """Terms that are neither mapped nor Learn topic names are dropped."""
    assert taxonomy.map_terms(["Underwater Basket Weaving", "Geology"]) == [
        "Earth Science",
        "Science & Math",
    ]


def test_studio_paths_drops_a_root_implied_by_a_child(taxonomy):
    """
    A root path is dropped when a child path already implies it.

    Learn's ETL re-adds ancestors when it reads the field back, so keeping the
    root would only duplicate it.
    """
    assert taxonomy.studio_paths(["Science & Math", "Physics"]) == [
        ["Science & Math", "Physics"]
    ]


def test_studio_paths_keeps_a_root_with_no_child_selected(taxonomy):
    """A topic with no parent renders as a single-element path."""
    assert taxonomy.studio_paths(["Humanities", "Engineering"]) == [
        ["Engineering"],
        ["Humanities"],
    ]


def test_explicit_parent_uuid_nests_an_unnested_node(tmp_path):
    """A top-level node's `parent:` UUID resolves to that topic's name."""
    topics = [
        topic_node("Science & Math", SCIENCE_ID, mappings={"ocw": ["Science"]}),
        topic_node(
            "Physics", PHYSICS_ID, mappings={"ocw": ["Physics"]}, parent=SCIENCE_ID
        ),
    ]

    taxonomy = TopicTaxonomy.from_yaml(write_topics_yaml(tmp_path, topics))

    assert taxonomy.ancestors("Physics") == ["Science & Math"]
    assert taxonomy.studio_paths(["Physics"]) == [["Science & Math", "Physics"]]


def test_parent_uuid_is_ignored_on_a_nested_node(tmp_path):
    """
    Nesting wins over a nested node's own `parent:` UUID.

    Mirrors Learn's _walk_topic_map, which consults `parent` only for nodes
    that are not already nested under another topic.
    """
    topics = [
        topic_node("Humanities", HUMANITIES_ID),
        topic_node(
            "Science & Math",
            SCIENCE_ID,
            children=[
                topic_node(
                    "Physics",
                    PHYSICS_ID,
                    mappings={"ocw": ["Physics"]},
                    parent=HUMANITIES_ID,
                )
            ],
        ),
    ]

    taxonomy = TopicTaxonomy.from_yaml(write_topics_yaml(tmp_path, topics))

    assert taxonomy.ancestors("Physics") == ["Science & Math"]


def test_from_yaml_tolerates_null_children_and_null_nodes(tmp_path):
    """A null `children:` value and a null entry in a node list are skipped."""
    topics = [
        {
            "id": SCIENCE_ID,
            "name": "Science & Math",
            "mappings": {"ocw": ["Science"]},
            "children": None,
        },
        None,
    ]

    taxonomy = TopicTaxonomy.from_yaml(write_topics_yaml(tmp_path, topics))

    assert taxonomy.map_terms(["Science"]) == ["Science & Math"]


def test_repeated_topic_name_keeps_the_last_nodes_mappings(tmp_path):
    """A topic name appearing twice keeps only the last node's mapping rows."""
    topics = [
        topic_node("Physics", PHYSICS_ID, mappings={"ocw": ["Mechanics"]}),
        topic_node("Physics", PHYSICS_ID, mappings={"ocw": ["Quantum Mechanics"]}),
    ]

    taxonomy = TopicTaxonomy.from_yaml(write_topics_yaml(tmp_path, topics))

    assert taxonomy.map_terms(["Quantum Mechanics"]) == ["Physics"]
    assert taxonomy.map_terms(["Mechanics"]) == []


def test_ancestors_stops_on_a_parent_cycle():
    """A cyclic parent chain terminates instead of looping forever."""
    taxonomy = TopicTaxonomy({"A": "B", "B": "A"}, {})

    assert taxonomy.ancestors("A") == ["B"]


# ---------------------------------------------------------------------------
# learn_topic_options: what a starter's mit_learn_topics field actually offers
# ---------------------------------------------------------------------------


def test_learn_topic_options_returns_none_without_the_field():
    """A starter defining no mit_learn_topics field yields None, not an empty set."""
    assert learn_topic_options(make_starter(options_map=None)) is None


def test_learn_topic_options_includes_roots_and_child_paths():
    """
    Both `(root,)` and `(root, child)` selections count as offered.

    A root whose value is null (rather than a mapping of children) contributes
    only itself.
    """
    starter = make_starter(
        options_map={"Humanities": {"Language": []}, "Engineering": None}
    )

    assert learn_topic_options(starter) == {
        ("Engineering",),
        ("Humanities",),
        ("Humanities", "Language"),
    }


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def test_writes_mapped_topics(topics_yaml):
    """Mapped OCW topics are written as mit_learn_topics paths."""
    content = make_site(topics=[["Science", "Physics", "Quantum Mechanics"]])

    result = run_command(topics_yaml)

    content.refresh_from_db()
    assert content.metadata["mit_learn_topics"] == [["Science & Math", "Physics"]]
    assert result.outcomes == {UPDATED: 1}
    assert "Wrote mit_learn_topics for 1 sites" in result.out


def test_writes_every_topic_an_ocw_name_maps_to(topics_yaml):
    """An OCW name claimed by topics under two roots writes both paths."""
    content = make_site(topics=[["Energy", "Climate"]])

    run_command(topics_yaml)

    content.refresh_from_db()
    assert content.metadata["mit_learn_topics"] == [
        ["Energy, Climate & Sustainability", "Climate Science"],
        ["Science & Math", "Earth Science"],
    ]


def test_null_segments_in_ocw_topics_are_stripped(topics_yaml):
    """Legacy rows can carry nulls inside a topics path; they are ignored."""
    content = make_site(topics=[["Science", None]])

    run_command(topics_yaml)

    content.refresh_from_db()
    assert content.metadata["mit_learn_topics"] == [["Science & Math"]]


@pytest.mark.parametrize("topics", [None, [], [[]], [[None]]])
def test_sites_without_usable_ocw_topics_are_skipped(topics_yaml, topics):
    """No usable OCW topics means nothing is written."""
    content = make_site(topics=topics)

    result = run_command(topics_yaml)

    content.refresh_from_db()
    assert "mit_learn_topics" not in content.metadata
    assert result.outcomes == {SKIPPED_NO_TOPICS: 1}


def test_existing_value_is_left_alone_by_default(topics_yaml):
    """A curated mit_learn_topics value is not overwritten without --overwrite."""
    curated = [["Humanities"]]
    content = make_site(topics=[["Science", "Physics"]], learn_topics=curated)

    result = run_command(topics_yaml)

    content.refresh_from_db()
    assert content.metadata["mit_learn_topics"] == curated
    assert result.outcomes == {SKIPPED_CURATED: 1}


def test_overwrite_replaces_an_existing_value(topics_yaml):
    """--overwrite replaces a value that is already set."""
    content = make_site(topics=[["Science", "Physics"]], learn_topics=[["Humanities"]])

    result = run_command(topics_yaml, overwrite=True)

    content.refresh_from_db()
    assert content.metadata["mit_learn_topics"] == [["Science & Math", "Physics"]]
    assert result.outcomes == {UPDATED: 1}


def test_value_already_equal_to_the_mapping_is_left_unchanged(topics_yaml):
    """An existing value equal to the mapped one is reported, not rewritten."""
    content = make_site(
        topics=[["Science", "Physics"]], learn_topics=[["Science & Math", "Physics"]]
    )

    result = run_command(topics_yaml, overwrite=True)

    assert result.outcomes == {UNCHANGED: 1}
    assert "Wrote mit_learn_topics for 0 sites" in result.out
    assert website_flags(content.website) == (False, False)


def test_topics_that_map_to_nothing_are_skipped(topics_yaml):
    """OCW topics that resolve to no Learn topic write nothing."""
    content = make_site(topics=[["Underwater Basket Weaving"]])

    result = run_command(topics_yaml)

    content.refresh_from_db()
    assert "mit_learn_topics" not in content.metadata
    assert result.outcomes == {NOTHING_MAPPED: 1}


def test_starter_without_the_learn_field_is_skipped(topics_yaml):
    """Some starters (ocw-course-v3) define `topics` but no mit_learn_topics."""
    content = make_site(
        topics=[["Science", "Physics"]], starter=make_starter(options_map=None)
    )

    result = run_command(topics_yaml)

    content.refresh_from_db()
    assert "mit_learn_topics" not in content.metadata
    assert result.outcomes == {SKIPPED_NO_FIELD: 1}


def test_site_without_a_starter_is_skipped(topics_yaml):
    """A site with no starter has no field to validate the mapping against."""
    content = make_site(topics=[["Science", "Physics"]], starter=None)

    result = run_command(topics_yaml)

    content.refresh_from_db()
    assert "mit_learn_topics" not in content.metadata
    assert result.outcomes == {SKIPPED_NO_FIELD: 1}


@pytest.mark.parametrize("with_starter", [True, False])
def test_ignore_config_writes_when_the_field_is_missing(topics_yaml, with_starter):
    """--ignore-config writes even with no mit_learn_topics field to check against."""
    starter = make_starter(options_map=None) if with_starter else None
    content = make_site(topics=[["Science", "Physics"]], starter=starter)

    result = run_command(topics_yaml, ignore_config=True)

    content.refresh_from_db()
    assert content.metadata["mit_learn_topics"] == [["Science & Math", "Physics"]]
    assert result.outcomes == {UPDATED: 1}


def test_path_the_starter_does_not_offer_is_skipped_and_reported(topics_yaml):
    """A mapped path the starter's field does not offer is refused and named."""
    starter = make_starter(options_map={"Engineering": {"Computer Science": []}})
    content = make_site(
        topics=[["Energy", "Climate"]], starter=starter, name="narrow-site"
    )

    result = run_command(topics_yaml)

    content.refresh_from_db()
    assert "mit_learn_topics" not in content.metadata
    assert result.outcomes == {INVALID_PATHS: 1}
    assert "narrow-site" in result.err
    assert "Energy, Climate & Sustainability / Climate Science" in result.err
    assert "Science & Math / Earth Science" in result.err
    assert f"not offered by starter {starter.slug}" in result.err


def test_ignore_config_writes_paths_the_starter_does_not_offer(topics_yaml):
    """--ignore-config bypasses the starter options check entirely."""
    starter = make_starter(options_map={"Engineering": {"Computer Science": []}})
    content = make_site(topics=[["Energy", "Climate"]], starter=starter)

    result = run_command(topics_yaml, ignore_config=True)

    content.refresh_from_db()
    assert content.metadata["mit_learn_topics"] == [
        ["Energy, Climate & Sustainability", "Climate Science"],
        ["Science & Math", "Earth Science"],
    ]
    assert result.err == ""


def test_dry_run_changes_nothing(topics_yaml):
    """--dry-run reports the update but leaves the database untouched."""
    content = make_site(topics=[["Science", "Physics"]])
    before = sync_checksum(content)

    result = run_command(topics_yaml, dry_run=True)

    content.refresh_from_db()
    assert "mit_learn_topics" not in content.metadata
    assert website_flags(content.website) == (False, False)
    assert sync_checksum(content) == before
    assert result.outcomes == {UPDATED: 1}
    assert "Dry run: 1 sites would have mit_learn_topics written" in result.out


def test_writing_marks_the_site_for_republish_and_resyncs_state(topics_yaml):
    """
    Each write goes through WebsiteContent.save() rather than bulk_update.

    save() flags the site as having unpublished draft and live changes, and the
    post_save receiver refreshes the ContentSyncState checksum; a bulk_update
    would have skipped both, and the change would never reach the built site.
    """
    content = make_site(topics=[["Science", "Physics"]])
    before = sync_checksum(content)

    run_command(topics_yaml)

    content.refresh_from_db()
    assert website_flags(content.website) == (True, True)
    assert sync_checksum(content) != before
    assert sync_checksum(content) == content.calculate_checksum()


def test_only_sitemetadata_content_is_considered(topics_yaml):
    """Topics on other content types are not touched."""
    page = WebsiteContentFactory.create(
        website=WebsiteFactory.create(starter=make_starter()),
        type=CONTENT_TYPE_PAGE,
        metadata={"topics": [["Science", "Physics"]]},
    )

    result = run_command(topics_yaml)

    page.refresh_from_db()
    assert "mit_learn_topics" not in page.metadata
    assert "Examined 0 sitemetadata objects" in result.out


@pytest.mark.parametrize(
    "options", [{"filter": "kept-site"}, {"exclude": "other-site"}]
)
def test_filter_options_scope_the_run(topics_yaml, options):
    """--filter and --exclude restrict which sites are processed."""
    kept = make_site(topics=[["Science", "Physics"]], name="kept-site")
    other = make_site(topics=[["Science", "Physics"]], name="other-site")

    result = run_command(topics_yaml, **options)

    kept.refresh_from_db()
    other.refresh_from_db()
    assert kept.metadata["mit_learn_topics"] == [["Science & Math", "Physics"]]
    assert "mit_learn_topics" not in other.metadata
    assert "Examined 1 sitemetadata objects" in result.out


def test_starter_option_scopes_the_run_to_one_starter(topics_yaml):
    """--starter processes only sites built on that starter slug."""
    course_site = make_site(
        topics=[["Science", "Physics"]], starter=make_starter(slug="ocw-course-v2")
    )
    www_site = make_site(
        topics=[["Science", "Physics"]], starter=make_starter(slug="ocw-www")
    )

    run_command(topics_yaml, starter="ocw-course-v2")

    course_site.refresh_from_db()
    www_site.refresh_from_db()
    assert course_site.metadata["mit_learn_topics"] == [["Science & Math", "Physics"]]
    assert "mit_learn_topics" not in www_site.metadata


def test_report_lists_every_examined_site(topics_yaml, tmp_path):
    """--report writes a row per examined site, skipped sites included."""
    starter = make_starter(slug="ocw-course-v2")
    make_site(topics=[["Science", "Physics"]], starter=starter, name="updated-site")
    make_site(
        topics=[["Science", "Physics"]],
        learn_topics=[["Humanities"]],
        starter=starter,
        name="curated-site",
    )
    report = tmp_path / "report.csv"

    result = run_command(topics_yaml, report=str(report))

    rows = {
        row["website"]: row for row in csv.DictReader(report.read_text().splitlines())
    }
    assert rows["updated-site"] == {
        "website": "updated-site",
        "starter": "ocw-course-v2",
        "ocw_topics": "Science / Physics",
        "existing_mit_learn_topics": "",
        "proposed_mit_learn_topics": "Science & Math / Physics",
        "outcome": UPDATED,
    }
    assert rows["curated-site"]["existing_mit_learn_topics"] == "Humanities"
    assert rows["curated-site"]["proposed_mit_learn_topics"] == ""
    assert rows["curated-site"]["outcome"] == SKIPPED_CURATED
    assert f"Wrote report for 2 sites to {report}" in result.out


def test_verbose_output_names_each_site(topics_yaml):
    """-v2 lists the value written per site, and why a site was skipped."""
    make_site(topics=[["Science", "Physics"]], name="written-site")
    make_site(topics=[["Underwater Basket Weaving"]], name="unmapped-site")

    result = run_command(topics_yaml, verbosity=2)

    assert "written-site: Science & Math / Physics" in result.out
    assert f"unmapped-site: {NOTHING_MAPPED}" in result.out


def test_summary_tallies_every_outcome(topics_yaml):
    """The summary counts each outcome across the sites examined."""
    make_site(topics=[["Science", "Physics"]])
    make_site(topics=[])
    make_site(topics=[["Underwater Basket Weaving"]])
    make_site(topics=[["Science", "Physics"]], learn_topics=[["Humanities"]])
    make_site(topics=[["Science", "Physics"]], starter=make_starter(options_map=None))

    result = run_command(topics_yaml)

    assert result.outcomes == {
        UPDATED: 1,
        SKIPPED_NO_TOPICS: 1,
        NOTHING_MAPPED: 1,
        SKIPPED_CURATED: 1,
        SKIPPED_NO_FIELD: 1,
    }
    assert "Examined 5 sitemetadata objects" in result.out
