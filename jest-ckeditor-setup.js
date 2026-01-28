/* eslint-env jest */ /**
 * Patch CKEditor's version checker to prevent false-positive duplication errors in tests
 *
 * The ckeditor5-math package (v36.0.2) bundles its own @ckeditor dependencies (v36.0.1),
 * while our main packages are at v35.4.0. This causes CKEditor's version checker to detect
 * "duplicated modules" even though they're not actually running in the same context in our
 * test environment.
 *
 * This setup file runs before jest.setup.js and prevents the error by mocking the
 * version module before any CKEditor modules load. The mock returns our main version
 * (35.4.0) to satisfy the checker without affecting functionality.
 */

// Mock all @ckeditor version.js modules to prevent duplication errors
// Using our main CKEditor version (35.4.0)
jest.mock(
  "@ckeditor/ckeditor5-utils/src/version",
  () => {
    return "35.4.0"
  },
  { virtual: false },
)

// Also mock ckeditor5-math's bundled version (36.0.1) to prevent conflicts
jest.mock(
  "ckeditor5-math/node_modules/@ckeditor/ckeditor5-utils/src/version",
  () => {
    return "35.4.0"
  },
  { virtual: false },
)
