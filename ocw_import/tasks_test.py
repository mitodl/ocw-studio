""" Tests for ocw_import.tasks """

import pytest
from moto import mock_s3

from ocw_import.conftest import MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, setup_s3
from ocw_import.tasks import (
    fetch_ocw2hugo_course_paths,
    import_ocw2hugo_course_paths,
    import_ocw2hugo_courses,
    update_ocw2hugo_course_paths,
    update_ocw_resource_data,
)


# pylint:disable=too-many-arguments
pytestmark = pytest.mark.django_db

ALL_COURSES_FILTER = [
    "1-050-engineering-mechanics-i-fall-2007",
    "1-201j-transportation-systems-analysis-demand-and-economics-fall-2008",
    "biology",
    "es-s41-speak-italian-with-your-mouth-full-spring-2012",
]
ALL_COURSES_PATHS = [
    "1-050-engineering-mechanics-i-fall-2007/data/course_legacy.json",
    "1-201j-transportation-systems-analysis-demand-and-economics-fall-2008/data/course_legacy.json",
    "biology/data/course_legacy.json",
    "es-s41-speak-italian-with-your-mouth-full-spring-2012/data/course_legacy.json",
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
    settings.OCW_COURSE_STARTER_SLUG = "ocw-course-v2"
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


@pytest.mark.parametrize(
    "paths", [["1-050-mechanical-engineering", "3-34-transportation-systems"], [], None]
)
@pytest.mark.parametrize("create_new_content", [True, False])
def test_update_ocw2hugo_course_paths(mocker, paths, create_new_content):
    """ update_ocw2hugo_course should be called from task with correct kwargs """
    mock_update_course = mocker.patch("ocw_import.tasks.update_ocw2hugo_course")
    update_ocw2hugo_course_paths.delay(
        paths,
        MOCK_BUCKET_NAME,
        TEST_OCW2HUGO_PREFIX,
        "title",
        create_new_content=create_new_content,
    )
    if not paths:
        mock_update_course.assert_not_called()
    else:
        for path in paths:
            mock_update_course.assert_any_call(
                MOCK_BUCKET_NAME,
                TEST_OCW2HUGO_PREFIX,
                path,
                "title",
                create_new_content=create_new_content,
            )


@mock_s3
@pytest.mark.parametrize(
    "chunk_size, filter_list, limit, call_count",
    [
        [1, ALL_COURSES_FILTER, None, 4],
        [1, ["1-050-engineering-mechanics-i-fall-2007"], None, 1],
        [2, ALL_COURSES_FILTER, None, 2],
        [1, ALL_COURSES_FILTER, 1, 1],
    ],
)
def test_import_ocw2hugo_courses(
    settings, mocked_celery, mocker, filter_list, chunk_size, limit, call_count
):
    """
    import_ocw2hugo_course_paths should be called correct # times for given chunk size, limit, filter, and # of paths
    """
    setup_s3(settings)
    mock_import_paths = mocker.patch("ocw_import.tasks.import_ocw2hugo_course_paths.si")
    course_paths = list(
        fetch_ocw2hugo_course_paths(
            MOCK_BUCKET_NAME, prefix=TEST_OCW2HUGO_PREFIX, filter_list=filter_list
        )
    )
    with pytest.raises(mocked_celery.replace_exception_class):
        import_ocw2hugo_courses.delay(
            bucket_name=MOCK_BUCKET_NAME,
            course_paths=course_paths,
            prefix=TEST_OCW2HUGO_PREFIX,
            chunk_size=chunk_size,
            limit=limit,
        )
    assert mock_import_paths.call_count == call_count


@mock_s3
def test_import_ocw2hugo_courses_no_bucket(settings, mocker):
    """ import_ocw2hugo_courses should throw an error if a bucket is not specified """
    setup_s3(settings)
    mock_import_paths = mocker.patch("ocw_import.tasks.import_ocw2hugo_course_paths.si")
    course_paths = list(
        fetch_ocw2hugo_course_paths(
            MOCK_BUCKET_NAME,
            prefix=TEST_OCW2HUGO_PREFIX,
            filter_list=ALL_COURSES_FILTER,
        )
    )
    with pytest.raises(TypeError):
        import_ocw2hugo_courses.delay(  # pylint:disable=no-value-for-parameter
            bucket_name=None,
            prefix=TEST_OCW2HUGO_PREFIX,
            course_paths=course_paths,
            chunk_size=100,
        )
    assert mock_import_paths.call_count == 0


def test_import_ocw2hugo_courses_no_filter(mocker):
    """ import_ocw2hugo_courses should throw an error if course_paths is not specified """
    mock_import_paths = mocker.patch("ocw_import.tasks.import_ocw2hugo_course_paths.si")
    with pytest.raises(TypeError):
        import_ocw2hugo_courses.delay(  # pylint:disable=no-value-for-parameter
            bucket_name=MOCK_BUCKET_NAME, prefix=TEST_OCW2HUGO_PREFIX, chunk_size=100
        )
    assert mock_import_paths.call_count == 0


@mock_s3
@pytest.mark.parametrize(
    "chunk_size, filter_list, limit, call_count",
    [
        [1, None, None, 4],
        [1, ["1-050-engineering-mechanics-i-fall-2007"], None, 1],
        [2, None, None, 2],
        [1, None, 1, 1],
    ],
)
@pytest.mark.parametrize("create_new_content", [True, False])
def test_update_ocw_resource_data(
    settings,
    mocked_celery,
    mocker,
    filter_list,
    chunk_size,
    limit,
    call_count,
    create_new_content,
):
    """
    update_ocw2hugo_course_paths should be called correct # times for given chunk size, limit, filter, and # of paths
    """
    setup_s3(settings)
    mock_update_paths = mocker.patch("ocw_import.tasks.update_ocw2hugo_course_paths.si")
    with pytest.raises(mocked_celery.replace_exception_class):
        update_ocw_resource_data.delay(
            bucket_name=MOCK_BUCKET_NAME,
            prefix=TEST_OCW2HUGO_PREFIX,
            chunk_size=chunk_size,
            filter_list=filter_list,
            limit=limit,
            content_field="title",
            create_new_content=create_new_content,
        )
    assert mock_update_paths.call_count == call_count


def test_import_ocw2hugo_courses_missing_required_fields(mocker):
    """ update_ocw2hugo_course_paths should be called zero times if required fields are missing """
    mock_update_paths = mocker.patch("ocw_import.tasks.update_ocw2hugo_course_paths.si")
    with pytest.raises(TypeError):
        update_ocw_resource_data.delay(  # pylint:disable=no-value-for-parameter
            bucket_name=None,
            prefix=TEST_OCW2HUGO_PREFIX,
            chunk_size=100,
            content_field="title",
        )
    assert mock_update_paths.call_count == 0

    with pytest.raises(TypeError):
        update_ocw_resource_data.delay(  # pylint:disable=no-value-for-parameter
            bucket_name=MOCK_BUCKET_NAME,
            prefix=TEST_OCW2HUGO_PREFIX,
            chunk_size=100,
            content_field=None,
        )
    assert mock_update_paths.call_count == 0
