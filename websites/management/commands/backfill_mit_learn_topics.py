"""Backfill mit_learn_topics metadata from OCW topics via topics.yaml"""  # noqa: INP001

import csv
from collections import Counter
from pathlib import Path

import yaml
from django.db import transaction

from main.management.commands.filter import WebsiteFilterCommand
from websites.constants import CONTENT_TYPE_METADATA
from websites.models import WebsiteContent, WebsiteStarter
from websites.site_config_api import SiteConfig

OCW_TOPICS_FIELD = "topics"
LEARN_TOPICS_FIELD = "mit_learn_topics"
OFFEROR_CODE = "ocw"

UPDATED = "updated"
UNCHANGED = "unchanged"
SKIPPED_CURATED = "skipped: mit_learn_topics already set"
SKIPPED_NO_TOPICS = "skipped: no ocw topics"
SKIPPED_NO_FIELD = "skipped: starter has no mit_learn_topics field"
NOTHING_MAPPED = "skipped: ocw topics map to nothing"
INVALID_PATHS = "skipped: mapped topic is not a config option"


class TopicTaxonomy:
    """
    topics.yaml reduced to what the OCW mapping needs.

    Mirrors MIT Learn's own pipeline: _walk_topic_map builds the topic tree and
    the offeror mapping rows, transform_topics resolves a name against them, and
    load_topics adds each resolved topic's ancestors.
    """

    def __init__(self, parents: dict[str, str | None], mappings: dict[str, list[str]]):
        self.parents = parents
        self.mappings = mappings
        self.topic_names = set(parents)

    @classmethod
    def from_yaml(  # noqa: C901
        cls, path: str, offeror_code: str = OFFEROR_CODE
    ) -> TopicTaxonomy:
        """Build a taxonomy from a topics.yaml file"""
        document = yaml.safe_load(Path(path).read_text())
        roots = document["topics"]

        uuids: dict[str, str] = {}

        def index(nodes):
            for node in nodes or []:
                if node and node.get("id"):
                    uuids[str(node["id"])] = node["name"]
                if node:
                    index(node.get("children"))

        index(roots)

        parents: dict[str, str | None] = {}
        per_topic: dict[str, list[str]] = {}
        order: list[str] = []

        def walk(nodes, parent=None):
            for node in nodes or []:
                if not node:
                    continue
                name = node["name"]
                resolved = parent
                # An explicit `parent:` UUID applies only to un-nested nodes,
                # matching _walk_topic_map.
                if parent is None and node.get("parent"):
                    resolved = uuids.get(str(node["parent"]))
                parents[name] = resolved
                # Mapping rows are replaced, not merged: a repeated topic name
                # keeps only the last node's names.
                node_mappings = node.get("mappings") or {}
                per_topic[name] = list(node_mappings.get(offeror_code) or [])
                if name not in order:
                    order.append(name)
                walk(node.get("children"), name)

        walk(roots)

        mappings: dict[str, list[str]] = {}
        for topic_name in order:
            for source_name in per_topic[topic_name]:
                targets = mappings.setdefault(source_name, [])
                if topic_name not in targets:
                    targets.append(topic_name)

        return cls(parents, mappings)

    def ancestors(self, name: str) -> list[str]:
        """Walk a topic's parent chain upward"""
        chain, seen = [], {name}
        parent = self.parents.get(name)
        while parent and parent not in seen:
            chain.append(parent)
            seen.add(parent)
            parent = self.parents.get(parent)
        return chain

    def map_terms(self, terms: list[str]) -> list[str]:
        """
        Resolve OCW topic names to Learn topic names.

        Exact match against the mapping rows first, fanning out to every mapped
        topic; then a pass-through for names that are themselves Learn topics;
        anything else is dropped.
        """
        resolved: set[str] = set()
        for term in terms:
            if term in self.mappings:
                resolved.update(self.mappings[term])
            elif term in self.topic_names:
                resolved.add(term)
        for name in list(resolved):
            resolved.update(self.ancestors(name))
        return sorted(resolved)

    def studio_paths(self, topic_names: list[str]) -> list[list[str]]:
        """
        Render Learn topic names as hierarchical-select paths, [[topic, subtopic]].

        A root path is dropped when a child path already implies it, since the
        Learn ETL re-adds ancestors when it reads the field back.
        """
        paths: list[list[str]] = []
        for name in sorted(set(topic_names)):
            parent = self.parents.get(name)
            path = [parent, name] if parent else [name]
            if path not in paths:
                paths.append(path)
        implied = {path[0] for path in paths if len(path) > 1}
        return [p for p in paths if len(p) > 1 or p[0] not in implied]


def learn_topic_options(starter: WebsiteStarter) -> set[tuple[str, ...]] | None:
    """
    Return the selections the starter's mit_learn_topics field actually offers.

    Returns None when the starter has no such field at all -- ocw-course-v3 and
    the localdev course config define `topics` but not `mit_learn_topics`.
    """
    for config_field in SiteConfig(starter.config).iter_fields():
        field = config_field.field
        if field.get("name") != LEARN_TOPICS_FIELD:
            continue
        options_map = field.get("options_map") or {}
        options = {(root,) for root in options_map}
        for root, children in options_map.items():
            for child in children or {}:
                options.add((root, child))
        return options
    return None


class Command(WebsiteFilterCommand):
    """
    Write mit_learn_topics into sitemetadata, mapped from each site's ocw topics.

    Reads metadata['topics'], resolves it through a MIT Learn topics.yaml, and
    stores the result in metadata['mit_learn_topics'] as [topic, subtopic] paths.
    Saving marks each touched site as having unpublished draft and live changes,
    so the sites need republishing for the change to reach the built output.
    """

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "topics_yaml",
            help="Path to MIT Learn's learning_resources/data/topics.yaml",
        )
        parser.add_argument(
            "-s",
            "--starter",
            dest="starter",
            default=None,
            help="Only process sites built on this WebsiteStarter slug",
        )
        parser.add_argument(
            "-o",
            "--overwrite",
            dest="overwrite",
            action="store_true",
            help="Replace mit_learn_topics values that are already set",
        )
        parser.add_argument(
            "-d",
            "--dry-run",
            dest="dry_run",
            action="store_true",
            help="Report what would change without writing anything",
        )
        parser.add_argument(
            "--ignore-config",
            dest="ignore_config",
            action="store_true",
            help=(
                "Write mapped topics even when the starter has no "
                "mit_learn_topics field or does not offer the mapped option"
            ),
        )
        parser.add_argument(
            "-r",
            "--report",
            dest="report",
            default=None,
            help="Write a per-site CSV of the proposed values to this path",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        taxonomy = TopicTaxonomy.from_yaml(options["topics_yaml"])
        dry_run = options["dry_run"]
        overwrite = options["overwrite"]
        ignore_config = options["ignore_config"]
        verbose = options["verbosity"] > 1

        contents = WebsiteContent.objects.filter(
            type=CONTENT_TYPE_METADATA
        ).select_related("website", "website__starter")
        contents = self.filter_website_contents(website_contents=contents)
        if options["starter"]:
            contents = contents.filter(website__starter__slug=options["starter"])

        options_cache: dict[int, set[tuple[str, ...]] | None] = {}
        outcomes = Counter()
        rows = []
        to_save = []

        for content in contents.iterator():
            starter = content.website.starter
            if starter and starter.id not in options_cache:
                options_cache[starter.id] = learn_topic_options(starter)
            allowed = options_cache.get(starter.id) if starter else None

            outcome, proposed, existing, terms = self.evaluate(
                content,
                taxonomy,
                allowed=allowed,
                overwrite=overwrite,
                ignore_config=ignore_config,
            )
            outcomes[outcome] += 1
            rows.append(
                {
                    "website": content.website.name,
                    "starter": starter.slug if starter else "",
                    "ocw_topics": "; ".join(" / ".join(p) for p in terms),
                    "existing_mit_learn_topics": "; ".join(
                        " / ".join(p) for p in existing
                    ),
                    "proposed_mit_learn_topics": "; ".join(
                        " / ".join(p) for p in proposed
                    ),
                    "outcome": outcome,
                }
            )
            if outcome == UPDATED:
                content.metadata[LEARN_TOPICS_FIELD] = proposed
                to_save.append(content)
                if verbose:
                    self.stdout.write(
                        f"{content.website.name}: "
                        + "; ".join(" / ".join(p) for p in proposed)
                    )
            elif verbose and outcome != UNCHANGED:
                self.stdout.write(f"{content.website.name}: {outcome}")

        if to_save and not dry_run:
            # One save() per object on purpose: the post_save receiver upserts
            # ContentSyncState, and WebsiteContent.save() flags the site as having
            # unpublished changes. bulk_update would skip both.
            with transaction.atomic():
                for content in to_save:
                    content.save()

        if options["report"]:
            self.write_report(options["report"], rows)

        self.write_summary(outcomes, len(to_save), dry_run=dry_run)

    def evaluate(  # noqa: PLR0911
        self,
        content: WebsiteContent,
        taxonomy: TopicTaxonomy,
        *,
        allowed: set[tuple[str, ...]] | None,
        overwrite: bool,
        ignore_config: bool,
    ) -> tuple[str, list[list[str]], list[list[str]], list[list[str]]]:
        """
        Decide what this site's mit_learn_topics should become.

        Returns the outcome plus the proposed value, the existing value, and the
        site's ocw topics, so the caller can report on skipped sites too.
        """
        metadata = content.metadata or {}
        # Legacy rows can carry nulls; the widget strips them on save.
        ocw_topics = [
            [term for term in path if term]
            for path in metadata.get(OCW_TOPICS_FIELD) or []
        ]
        existing = metadata.get(LEARN_TOPICS_FIELD) or []

        if allowed is None and not ignore_config:
            return SKIPPED_NO_FIELD, [], existing, ocw_topics
        if not any(ocw_topics):
            return SKIPPED_NO_TOPICS, [], existing, ocw_topics
        if existing and not overwrite:
            return SKIPPED_CURATED, [], existing, ocw_topics

        terms = sorted({term for path in ocw_topics for term in path})
        proposed = taxonomy.studio_paths(taxonomy.map_terms(terms))
        if not proposed:
            return NOTHING_MAPPED, [], existing, ocw_topics
        if allowed is not None and not ignore_config:
            unusable = [p for p in proposed if tuple(p) not in allowed]
            if unusable:
                self.stderr.write(
                    f"{content.website.name}: "
                    + ", ".join(" / ".join(p) for p in unusable)
                    + f" not offered by starter {content.website.starter.slug}"
                )
                return INVALID_PATHS, proposed, existing, ocw_topics
        if proposed == existing:
            return UNCHANGED, proposed, existing, ocw_topics
        return UPDATED, proposed, existing, ocw_topics

    def write_report(self, path: str, rows: list[dict]):
        """Write the per-site CSV report"""
        fieldnames = [
            "website",
            "starter",
            "ocw_topics",
            "existing_mit_learn_topics",
            "proposed_mit_learn_topics",
            "outcome",
        ]
        with Path(path).open("w", newline="") as report_file:
            writer = csv.DictWriter(report_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(f"Wrote report for {len(rows)} sites to {path}")

    def write_summary(self, outcomes: Counter, saved: int, *, dry_run: bool):
        """Write the run summary"""
        total = sum(outcomes.values())
        self.stdout.write(f"Examined {total} sitemetadata objects")
        for outcome, count in outcomes.most_common():
            self.stdout.write(f"  {count:>6}  {outcome}")
        if dry_run:
            self.stdout.write(
                f"Dry run: {saved} sites would have mit_learn_topics written"
            )
        else:
            self.stdout.write(f"Wrote mit_learn_topics for {saved} sites")
