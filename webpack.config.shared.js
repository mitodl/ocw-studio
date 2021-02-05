const path = require("path")
const webpack = require("webpack")
const CKEditorWebpackPlugin = require("@ckeditor/ckeditor5-dev-webpack-plugin")
const { styles } = require("@ckeditor/ckeditor5-dev-utils")

module.exports = {
  config: {
    entry: {
      root: "./static/js/index.tsx",
      style: "./static/js/entry/style"
    },
    module: {
      rules: [
        {
          // this regex is necessary to explicitly exclude ckeditor stuff
          test: /static\/.+\.(svg|ttf|woff|woff2|eot|gif)$/,
          use: "url-loader"
        },
        {
          test: /\.tsx?$/,
          use: "ts-loader",
          exclude: /node_modules/
        },
        {
          test: /ckeditor5-[^/\\]+[/\\]theme[/\\]icons[/\\][^/\\]+\.svg$/,
          use: ["raw-loader"]
        },
        {
          test: /ckeditor5-[^/\\]+[/\\]theme[/\\].+\.css$/,
          use: [
            {
              loader: "style-loader",
              options: {
                injectType: "singletonStyleTag",
                attributes: {
                  "data-cke": true
                }
              }
            },
            {
              loader: "postcss-loader",
              options: styles.getPostCssConfig({
                themeImporter: {
                  themePath: require.resolve("@ckeditor/ckeditor5-theme-lark")
                },
                minify: true
              })
            }
          ]
        }
      ]
    },
    resolve: {
      modules: [path.join(__dirname, "static/js"), "node_modules"],
      extensions: [".js", ".jsx", ".ts", ".tsx"]
    },
    performance: {
      hints: false
    }
  }
}
