"""main tasks"""
import celery


@celery.task
def chord_finisher(*args, **kwargs):  # pylint:disable=unused-argument
    """
    Dummy task to indicate a chord has finished processing, so the next step(s) can proceed
    https://stackoverflow.com/a/19018521
    """
    return True
