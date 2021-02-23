module.exports = {
  setupFilesAfterEnv: ["<rootDir>static/js/test_setup.ts"],
  cacheDirectory: ".jest-cache",
  transform: {
    "^.+\\.tsx?$": "ts-jest",
    "^.+\\.js$": "babel-jest",
  },
  moduleNameMapper: {
    "\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$":
      "<rootDir>/static/js/mocks/fileMock.js",
    "\\.(css|less)$": "<rootDir>/static/js/mocks/styleMock.js"
  },
  transformIgnorePatterns: [
    "/node_modules/(?!(" +
      "@ckeditor/*" +
      "|lodash-es" +
      ")/)"
  ],
  testPathIgnorePatterns: ["<rootDir>/staticfiles/", "<rootDir>/node_modules/"]
}
