const path = require("path")
const webpack = require("webpack")
const CKEditorWebpackPlugin = require("@ckeditor/ckeditor5-dev-webpack-plugin")
const { styles } = require("@ckeditor/ckeditor5-dev-utils")

module.exports = {
  entry: {
    ckeditor: "./static/ckeditor/CKEditor.ts",
    markdown: "./static/ckeditor/lib/markdown.ts"
  },
  output: {
    path: path.resolve("./static/js/lib/ckeditor/"),
    filename: "[name].js",
    crossOriginLoading: "anonymous",
    // library: "MyLibrary",
    libraryTarget: "commonjs-module",
    libraryExport: "default"
  },

  // output: {
  //   // The name under which the editor will be exported.
  //   library: 'ClassicEditor',

  //   path: path.resolve( __dirname, 'build' ),
  //   filename: 'ckeditor.js',
  //   libraryTarget: 'umd',
  //   libraryExport: 'default'
  // },


  plugins: [new CKEditorWebpackPlugin({ language: "en" ,
    addMainLanguageTranslationsToAllAssets: true
  })],

  module: {
    rules: [
      {
        // this regex is necessary to explicitly exclude ckeditor stuff
        test: /static\/.+\.(svg|ttf|woff|woff2|eot|gif)$/,
        use: "url-loader"
      },
      {
        test: /\.tsx?$/,
        exclude: /node_modules/,
        use: [
          {
            loader: "ts-loader",
            options: {
              onlyCompileBundledFiles: true,
              compilerOptions: {
              "module": "commonjs",
              "target": "es5",
              }
            }
          }
        ]
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
    modules: [path.join(__dirname, "static/ckeditor"), "node_modules"],
    extensions: [".js", ".jsx", ".ts", ".tsx"]
  },
  performance: {
    hints: false
  },
  optimization: {
    minimize: false
  }
}
