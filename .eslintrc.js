module.exports = {
  root: true,
  extends: ["eslint-config-mitodl", "eslint-config-mitodl/jest", "prettier"],
  rules: {
    "@typescript-eslint/no-explicit-any": "off",
  },
}
