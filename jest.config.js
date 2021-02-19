module.exports = {
  setupFilesAfterEnv: ["<rootDir>static/js/test_setup.ts"],
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
      "@ckeditor/ckeditor5-editor-classic" +
      "|@ckeditor/ckeditor5-engine" +
      "|@ckeditor/ckeditor5-core" +
      "|@ckeditor/ckeditor5-markdown-gfm" +
      "|@ckeditor/ckeditor5-utils" +
      "|@ckeditor/ckeditor5-ui" +
      "|@ckeditor/ckeditor5-essentials" +
      "|lodash-es" +
      ")/)"
  ],
  testPathIgnorePatterns: ["<rootDir>/staticfiles/", "<rootDir>/node_modules/"]
}
