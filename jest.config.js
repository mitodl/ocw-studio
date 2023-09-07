module.exports = {
  setupFilesAfterEnv: [
    // see https://github.com/ricardo-ch/jest-fail-on-console/issues/4
    "@testing-library/react-hooks/disable-error-filtering.js",
    "<rootDir>static/js/test_setup.ts",
  ],
  cacheDirectory: ".jest-cache",
  transform: { "^.+\\.(t|j)sx?$": ["@swc/jest"] },
  moduleNameMapper: {
    "\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$":
      "<rootDir>/static/js/mocks/fileMock.js",
    "\\.(css|less)$": "<rootDir>/static/js/mocks/styleMock.js",
  },
  // this here is a little bit of hackery! we need to mark a few modules in node_modules
  // not to *ignore* them but actually to include them in the transform. Jest doesn't have
  // a transformIncludePattern option, so this is how they recommend you explicitly include
  // code in node_modules. We need to do this because CKEditor code is distributed as ES6
  // modules with some webpack-specific syntax in it. This will ensure it gets transpiled
  // with Babel (this is cached between test runs so it doesn't have too much performance
  // overhead. See here for some details:
  // https://jestjs.io/docs/en/tutorial-react-native#transformignorepatterns-customization
  transformIgnorePatterns: [
    "/node_modules/(?!(" +
      "@ckeditor/*" +
      "|ckeditor5/*" +
      "|ckeditor5-math/*" +
      "|lodash-es" +
      ")/)",
  ],
  testPathIgnorePatterns: ["<rootDir>/staticfiles/", "<rootDir>/node_modules/"],
  testEnvironment: "jsdom",
  watchPlugins: [
    "jest-watch-typeahead/filename",
    "jest-watch-typeahead/testname",
  ],
}
