const path = require("path")
const webpack = require("webpack")

module.exports = {
  config: {
    entry: {
      root:         "./static/js/index.tsx",
      style:        "./static/js/entry/style",
    },
    module: {
      rules: [
        {
          test: /\.(svg|ttf|woff|woff2|eot|gif)$/,
          use:  "url-loader"
        },
        {
        test: /\.tsx?$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
      ]
    },
    resolve: {
      modules:    [path.join(__dirname, "static/js"), "node_modules"],
      extensions: [".js", ".jsx", ".ts", ".tsx"]
    },
    performance: {
      hints: false
    }
  }
}
