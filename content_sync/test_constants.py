"""Constants for tests in content_sync"""
UNEVEN_TAGS_TEST_FILE = "pipelines/definitions/concourse/test-pipeline-uneven.yml"
EVEN_TAGS_TEST_FILE = "pipelines/definitions/concourse/test-pipeline-even.yml"
EXPECTED_REMAINING_STRING_DEV = """bar: line 2
# START NON-DEV
baz: line 3
# END NON-DEV
qux: line 4"""
EXPECTED_REMAINING_STRING_NON_DEV = """# START DEV-ONLY
foo: line 1
# END DEV-ONLY
bar: line 2
qux: line 4"""
TEST_DEFAULT_HUGO_ARGS = {
    "--themesDir": "../ocw-hugo-themes",
    "--quiet": "",
    "--baseUrl": "/courses/course-1",
    "--config": "../ocw-hugo-projects/ocw-course-v2/config.yaml",
}
HUGO_ARG_TEST_OVERRIDES = [
    {"input": "--verbose", "output": {"--verbose": ""}},
    {"input": "--baseUrl / --verbose", "output": {"--baseUrl": "/", "--verbose": ""}},
    {
        "input": "--baseUrl / --verbose --debug",
        "output": {"--baseUrl": "/", "--verbose": "", "--debug": ""},
    },
    {
        "input": "--baseUrl / --verbose --debug --destination ./test_output",
        "output": {
            "--baseUrl": "/",
            "--verbose": "",
            "--debug": "",
            "--destination": "./test_output",
        },
    },
]
