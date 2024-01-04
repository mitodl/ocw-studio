from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules

from websites.management.commands.markdown_cleaning.cleaner import MarkdownCleanupRule

# Import all rule classes when `rules` module is loaded.
#
# Iterate through the modules in the current package
package_dir = Path(__file__).resolve().parent
for _, module_name, _ in iter_modules([str(package_dir)]):
    # import the module and iterate through its attributes
    module = import_module(f"{__name__}.{module_name}")
    for attribute_name in dir(module):
        attribute = getattr(module, attribute_name)

        if isclass(attribute) and issubclass(attribute, MarkdownCleanupRule):
            # Add the class to this package's variables
            globals()[attribute_name] = attribute
