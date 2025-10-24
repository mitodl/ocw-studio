"""Constants for markdown cleaning utilities."""

import re

# Hugo shortcode conversion regex patterns
# These patterns match Hugo shortcodes and are used to convert them to HTML
# equivalents. Hugo cannot parse nested shortcodes within shortcode parameters,
# so we convert to HTML.
#
# The regex patterns are designed to match INNERMOST shortcodes first using
# negated character classes that prevent matching across shortcode boundaries.
# The iterative approach in convert_shortcodes_to_html() then processes from
# inside out.

# Matches sup shortcodes with QUOTED parameters: {{< sup "content" >}}
#
# Pattern breakdown: \{\{<\s*sup\s+"([^"\\]*(?:\\.[^"\\]*)*)"\s*>\}\}
#   \{\{<           - Literal "{{<" (escaped braces)
#   \s*             - Optional whitespace
#   sup             - Literal "sup"
#   \s+             - Required whitespace
#   "               - Opening quote
#   ([^"\\]*        - Capture: Match any char EXCEPT " or \ (zero or more)
#     (?:\\.[^"\\]*)*) - Then match escaped chars (\") followed by more
#                       non-quote/backslash chars (zero or more times)
#   "               - Closing quote (stops at first unescaped quote)
#   \s*             - Optional whitespace
#   >\}\}           - Literal ">}}" (closing shortcode)
#
# The key: [^"\\]* stops at quotes, so nested {{< shortcodes inside
# quotes won't extend the match. This ensures we only capture content up to
# the first closing quote (innermost shortcode).
HUGO_SUP_QUOTED_PATTERN = re.compile(
    r'\{\{<\s*sup\s+"([^"\\]*(?:\\.[^"\\]*)*)"\s*>\}\}'
)

# Matches sup shortcodes with UNQUOTED parameters: {{< sup content >}}
#
# Pattern breakdown: \{\{<\s*sup\s+([^\s">]+)\s*>\}\}
#   \{\{<           - Literal "{{<"
#   \s*             - Optional whitespace
#   sup             - Literal "sup"
#   \s+             - Required whitespace
#   ([^\s">]+)      - Capture: Match any char EXCEPT whitespace, ", or >
#                     (matches one or more characters)
#   \s*             - Optional whitespace
#   >\}\}           - Literal ">}}" (closing shortcode)
#
# The key: [^\s">]+ stops at > or quotes, ensuring we match only to the
# shortcode's closing >. This prevents extending past the innermost
# shortcode boundary.
HUGO_SUP_UNQUOTED_PATTERN = re.compile(r'\{\{<\s*sup\s+([^\s">]+)\s*>\}\}')

# Matches sub shortcodes with QUOTED parameters: {{< sub "content" >}}
#
# Pattern breakdown: Same as HUGO_SUP_QUOTED_PATTERN but matches "sub"
# instead of "sup". See HUGO_SUP_QUOTED_PATTERN for detailed explanation.
HUGO_SUB_QUOTED_PATTERN = re.compile(
    r'\{\{<\s*sub\s+"([^"\\]*(?:\\.[^"\\]*)*)"\s*>\}\}'
)

# Matches sub shortcodes with UNQUOTED parameters: {{< sub content >}}
#
# Pattern breakdown: Same as HUGO_SUP_UNQUOTED_PATTERN but matches "sub"
# instead of "sup". See HUGO_SUP_UNQUOTED_PATTERN for detailed explanation.
HUGO_SUB_UNQUOTED_PATTERN = re.compile(r'\{\{<\s*sub\s+([^\s">]+)\s*>\}\}')

# Maximum iterations for nested shortcode conversion to prevent infinite loops
MAX_SHORTCODE_CONVERSION_ITERATIONS = 5
