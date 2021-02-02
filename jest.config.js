module.exports = {
  setupFilesAfterEnv: ["<rootDir>static/js/test_setup.ts"],
  transform: {
    "^.+\\.tsx?$": "ts-jest"
  },
  testPathIgnorePatterns: ["<rootDir>/staticfiles/", "<rootDir>/node_modules/"]
}
