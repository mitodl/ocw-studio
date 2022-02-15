import csv
import re
from collections import namedtuple
from typing import Callable, Iterable, Match

from websites.models import WebsiteContent


def progress_bar(
    iterable: Iterable,
    prefix="",
    suffix="",
    decimals=1,
    char_length=100,
    fill="█",
    printEnd="\r",
):
    """Call in a loop to create a terminal progress bar.

    Args:
        iterable (iterable): must implement __len__
        prefix   (str): prefix string
        suffix   (str): suffix string
        decimals (int): positive number of decimals in percent complete
        length   (int): character length of bar
        fill     (str): bar fill character
        printEnd (str): end character (e.g. "\r", "\r\n")

    Yields:
        The same items as `iterable`

    From https://stackoverflow.com/a/34325723/2747370
    """
    total = len(iterable)
    # Progress Bar Printing Function

    def print_progress_bar(iteration):
        percent = ("{0:." + str(decimals) + "f}").format(
            100 * (iteration / float(total))
        )
        filledLength = int(char_length * iteration // total)
        progress = fill * filledLength + "-" * (char_length - filledLength)
        print(f"\r{prefix} |{progress}| {percent}% {suffix}", end=printEnd)

    # Initial Call
    print_progress_bar(0)
    # Update Progress Bar
    for i, item in enumerate(iterable):
        yield item
        print_progress_bar(i + 1)
    # Print New Line on Complete
    print()
