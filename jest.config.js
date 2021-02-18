module.exports = {
  setupFilesAfterEnv: ["<rootDir>static/js/test_setup.ts"],
  transform: {
    "^.+\\.tsx?$": "ts-jest",
    "\\.jsx?$": "babel-jest"
  },
  // moduleNameMapper: {
  //   '^~/(.*)': '<rootDir>/src/$1',
  //   '\\.(css|scss)$': '<rootDir>/src/__mocks__/styleMock.js',
  // },

  moduleNameMapper: {
    "\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$": "<rootDir>/static/js/mocks/fileMock.js",
    "\\.(css|less)$": "<rootDir>/static/js/mocks/styleMock.js"
  },
  // transformIgnorePatterns: [
  //   "node_modules/(?!(ckeditor5-editor-classic|ckeditor5-core)/)"
  // ],
  transformIgnorePatterns: ['/node_modules/(?!@ckeditor|html2markdown)/.+\\.js$'],
  // transformIgnorePatterns: [''],
  testPathIgnorePatterns: ["<rootDir>/staticfiles/", "<rootDir>/node_modules/"]
}
