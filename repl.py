#!/usr/bin/env python3
"""Run Django shell with imported modules"""

if __name__ == "__main__":
    import os

    if not os.environ.get("PYTHONSTARTUP"):
        import sys
        from subprocess import check_call

        base_dir = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

        sys.exit(
            check_call(
                [  # noqa: S603
                    os.path.join(base_dir, "manage.py"),  # noqa: PTH118
                    "shell",
                    *sys.argv[1:],
                ],
                env={
                    **os.environ,
                    "PYTHONSTARTUP": os.path.join(base_dir, "repl.py"),  # noqa: PTH118
                },
            )
        )

    # put imports here used by PYTHONSTARTUP
    from django.conf import settings

    for app in settings.INSTALLED_APPS:
        try:  # noqa: SIM105
            # pylint: disable=exec-used
            exec(f"from {app}.models import *")  # noqa: S102
        except ModuleNotFoundError:
            pass
