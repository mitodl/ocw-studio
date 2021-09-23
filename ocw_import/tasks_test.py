""" Tests for ocw_import.tasks """
from tempfile import TemporaryDirectory

import pytest
from moto import mock_s3

from ocw_import.api import import_ocw2hugo_course
from ocw_import.conftest import (
    MOCK_BUCKET_NAME,
    TEST_OCW2HUGO_PREFIX,
    setup_s3,
    setup_s3_tmpdir,
)
from ocw_import.tasks import (
    delete_unpublished_courses,
    import_ocw2hugo_course_paths,
    import_ocw2hugo_courses,
)
from websites.models import Website


# pylint:disable=too-many-arguments
pytestmark = pytest.mark.django_db

ALL_COURSES_PATHS = [
    "1-050-engineering-mechanics-i-fall-2007/data/course_legacy.json",
    "1-201j-transportation-systems-analysis-demand-and-economics-fall-2008/data/course_legacy.json",
    "biology/data/course_legacy.json",
]
SINGLE_COURSE_PATHS = [
    "1-050-engineering-mechanics-i-fall-2007/data/course_legacy.json"
]


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
def test_delete_unpublished_courses(settings, course_starter):
    """ delete_unpublished_courses should remove Website objects when they aren't present in the passed in list of paths """
    setup_s3(settings)
    settings.OCW_IMPORT_STARTER_SLUG = "course"
    for course_path in ALL_COURSES_PATHS:
        import_ocw2hugo_course(
            MOCK_BUCKET_NAME,
            TEST_OCW2HUGO_PREFIX,
            course_path,
            starter_id=course_starter.id,
        )
    assert Website.objects.all().count() == 3
    delete_unpublished_courses(paths=ALL_COURSES_PATHS)
    assert Website.objects.all().count() == 3
    delete_unpublished_courses(paths=SINGLE_COURSE_PATHS)
    assert Website.objects.all().count() == 2


@mock_s3
def test_import_ocw2hugo_courses_delete_unpublished(settings, mocker, mocked_celery):
    """ import_ocw2hugo_courses should call delete_unpublished when courses have been removed from the ocw-to-hugo directory """
    mock_delete_unpublished_courses = mocker.patch(
        "ocw_import.tasks.delete_unpublished_courses.si"
    )
    tmpdir = TemporaryDirectory()
    setup_s3_tmpdir(settings, tmpdir.name)
    with pytest.raises(mocked_celery.replace_exception_class):
        import_ocw2hugo_courses.delay(
            bucket_name=MOCK_BUCKET_NAME, prefix=TEST_OCW2HUGO_PREFIX
        )
    mock_delete_unpublished_courses.assert_called_with(paths=ALL_COURSES_PATHS)
    tmpdir.cleanup()
    tmpdir = TemporaryDirectory()
    setup_s3_tmpdir(
        settings, tmpdir.name, courses=["1-050-engineering-mechanics-i-fall-2007"]
    )
    with pytest.raises(mocked_celery.replace_exception_class):
        import_ocw2hugo_courses.delay(
            bucket_name=MOCK_BUCKET_NAME, prefix=TEST_OCW2HUGO_PREFIX
        )
    mock_delete_unpublished_courses.assert_called_with(paths=SINGLE_COURSE_PATHS)
    tmpdir.cleanup()


@mock_s3
def test_import_ocw2hugo_courses_delete_unpublished_false(
    settings, mocker, mocked_celery
):
    """ import_ocw2hugo_courses should not call delete_unpublished when the argument is false """
    mock_delete_unpublished_courses = mocker.patch(
        "ocw_import.tasks.delete_unpublished_courses.si"
    )
    setup_s3(settings)
    with pytest.raises(mocked_celery.replace_exception_class):
        import_ocw2hugo_courses.delay(
            bucket_name=MOCK_BUCKET_NAME,
            prefix=TEST_OCW2HUGO_PREFIX,
            delete_unpublished=False,
        )
    mock_delete_unpublished_courses.assert_not_called()
