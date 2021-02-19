module.exports = {
  presets: [
    [
      "@babel/preset-env",
      {
        targets: {
          esmodules: false
        },
        useBuiltIns: "usage",
        corejs: { version: "3.9", proposals: true }
      }
    ]
  ]
}
