""" Tests for ocw_import.tasks """
from tempfile import TemporaryDirectory

import pytest
from moto import mock_s3

from ocw_import.conftest import (
    MOCK_BUCKET_NAME,
    TEST_OCW2HUGO_PREFIX,
    setup_s3,
    setup_s3_tmpdir,
)
from ocw_import.tasks import import_ocw2hugo_course_paths, import_ocw2hugo_courses
from websites.models import Website


# pylint:disable=too-many-arguments
pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "paths", [["1-050-mechanical-engineering", "3-34-transportation-systems"], [], None]
)
def test_import_ocw2hugo_course_paths(mocker, paths, course_starter, settings):
    """ mock_import_course should be called from task with correct kwargs """
    mock_import_course = mocker.patch("ocw_import.tasks.import_ocw2hugo_course")
    settings.OCW_IMPORT_STARTER_SLUG = "course"
    import_ocw2hugo_course_paths.delay(paths, MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX)
    if not paths:
        mock_import_course.assert_not_called()
    else:
        for path in paths:
            mock_import_course.assert_any_call(
                MOCK_BUCKET_NAME,
                TEST_OCW2HUGO_PREFIX,
                path,
                starter_id=course_starter.id,
            )


@mock_s3
@pytest.mark.parametrize(
    "chunk_size, filter_str, limit, call_count",
    [[1, None, None, 3], [1, "1-050", None, 1], [2, None, None, 2], [1, None, 1, 1]],
)
def test_import_ocw2hugo_courses(
    settings, mocked_celery, mocker, filter_str, chunk_size, limit, call_count
):
    """
    import_ocw2hugo_course_paths should be called correct # times for given chunk size, limit, filter, and # of paths
    """
    setup_s3(settings)
    mock_import_paths = mocker.patch("ocw_import.tasks.import_ocw2hugo_course_paths.si")
    with pytest.raises(mocked_celery.replace_exception_class):
        import_ocw2hugo_courses.delay(
            bucket_name=MOCK_BUCKET_NAME,
            prefix=TEST_OCW2HUGO_PREFIX,
            chunk_size=chunk_size,
            filter_str=filter_str,
            limit=limit,
        )
    assert mock_import_paths.call_count == call_count


def test_import_ocw2hugo_courses_nobucket(mocker):
    """ import_ocw2hugo_course_paths should be called correct # times for given chunk size and # of paths """
    mock_import_paths = mocker.patch("ocw_import.tasks.import_ocw2hugo_course_paths.si")
    with pytest.raises(TypeError):
        import_ocw2hugo_courses.delay(  # pylint:disable=no-value-for-parameter
            bucket_name=None, prefix=TEST_OCW2HUGO_PREFIX, chunk_size=100
        )
    assert mock_import_paths.call_count == 0


@mock_s3
def test_import_ocw2hugo_courses_delete_unpublished(settings, mocker, mocked_celery):
    mock_delete_unpublished_courses = mocker.patch(
        "ocw_import.tasks.delete_unpublished_courses.si"
    )
    settings.OCW_IMPORT_STARTER_SLUG = "course"
    tmpdir = TemporaryDirectory()
    setup_s3_tmpdir(settings, tmpdir.name)
    with pytest.raises(mocked_celery.replace_exception_class):
        import_ocw2hugo_courses.delay(
            bucket_name=MOCK_BUCKET_NAME, prefix=TEST_OCW2HUGO_PREFIX
        )
    mock_delete_unpublished_courses.assert_called_with(
        paths=[
            "/1-050-engineering-mechanics-i-fall-2007/data/course.json",
            "/1-201j-transportation-systems-analysis-demand-and-economics-fall-2008/data/course.json",
            "/biology/data/course.json",
        ]
    )
    tmpdir.cleanup()
    tmpdir = TemporaryDirectory()
    setup_s3_tmpdir(
        settings, tmpdir.name, courses=["1-050-engineering-mechanics-i-fall-2007"]
    )
    with pytest.raises(mocked_celery.replace_exception_class):
        import_ocw2hugo_courses.delay(
            bucket_name=MOCK_BUCKET_NAME, prefix=TEST_OCW2HUGO_PREFIX
        )
    mock_delete_unpublished_courses.assert_called_with(
        paths=["/1-050-engineering-mechanics-i-fall-2007/data/course.json"]
    )
    tmpdir.cleanup()
