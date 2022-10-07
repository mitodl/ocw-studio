module.exports = {
  parser: "@typescript-eslint/parser",
  plugins: ["@typescript-eslint"],
  extends: ["eslint-config-mitodl", "plugin:@typescript-eslint/recommended"],
  settings: {
    react: {
      version: "16.14.0"
    }
  },
  env: {
    browser: true,
    jquery: true,
    jest: true
  },
  rules: {
    "@typescript-eslint/no-explicit-any": "off",
    "@typescript-eslint/no-non-null-assertion": "off",
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "_", varsIgnorePattern: "_" },
    ],
    "mocha/no-top-level-hooks": "off",
    "mocha/no-sibling-hooks": "off",
    "mocha/no-global-tests": "off",
    "camelcase": [
      "error",
      {
        "properties": "never"
      }
    ]
  }
}
