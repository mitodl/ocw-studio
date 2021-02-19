module.exports = {
  setupFilesAfterEnv: ["<rootDir>static/js/test_setup.ts"],
  transform: {
    "^.+\\.[tj]sx?$": "ts-jest"
  },
  moduleNameMapper: {
    "\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$":
      "<rootDir>/static/js/mocks/fileMock.js",
    "\\.(css|less)$": "<rootDir>/static/js/mocks/styleMock.js"
  },
  transformIgnorePatterns: [
    "/node_modules/(?!" +
      "@ckeditor/ckeditor/ckeditor5-editor-classic" +
      "|@ckeditor/ckeditor/ckeditor5-editor-classic/src/classiceditor" +
      "|ckeditor" +
      ")/.+\\.js$"
  ],
  // |html2markdown|ckeditor|ckeditor5-editor-classic|@ckeditor/*)/.+\\.js$'],
  testPathIgnorePatterns: ["<rootDir>/staticfiles/", "<rootDir>/node_modules/"]
}
