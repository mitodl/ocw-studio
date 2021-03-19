""" Tests for ocw_import.tasks """
import pytest
from moto import mock_s3

from ocw_import.conftest import MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, setup_s3
from ocw_import.tasks import import_ocw2hugo_course_paths, import_ocw2hugo_courses


@pytest.mark.django_db
@pytest.mark.parametrize(
    "paths", [["1-050-mechanical-engineering", "3-34-transportation-systems"], [], None]
)
def test_import_ocw2hugo_course_paths(mocker, paths, course_starter):
    """ mock_import_course should be called from task with correct kwargs """
    mock_import_course = mocker.patch("ocw_import.tasks.import_ocw2hugo_course")
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
@pytest.mark.parametrize("chunk_size, call_count", [[1, 3], [2, 2]])
def test_import_ocw2hugo_courses(
    settings, mocked_celery, mocker, chunk_size, call_count
):
    """ import_ocw2hugo_course_paths should be called correct # times for given chunk size and # of paths """
    setup_s3(settings)
    mock_import_paths = mocker.patch("ocw_import.tasks.import_ocw2hugo_course_paths.si")
    with pytest.raises(mocked_celery.replace_exception_class):
        import_ocw2hugo_courses.delay(
            bucket_name=MOCK_BUCKET_NAME,
            prefix=TEST_OCW2HUGO_PREFIX,
            chunk_size=chunk_size,
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
