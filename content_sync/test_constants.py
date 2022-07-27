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
