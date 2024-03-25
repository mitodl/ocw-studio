"""main tasks"""

from main.celery import app


@app.task
def chord_finisher(*args, **kwargs):  # pylint:disable=unused-argument  # noqa: ARG001
    """
    Dummy task to indicate a chord has finished processing, so the next step(s) can proceed
    https://stackoverflow.com/a/19018521
    """  # noqa: E501, D401
    return True
