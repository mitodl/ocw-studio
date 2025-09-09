const webpack = require("webpack")
const path = require("path")
const BundleTracker = require("webpack-bundle-tracker")
const MiniCssExtractPlugin = require("mini-css-extract-plugin")
const { config } = require(path.resolve("./webpack.config.shared.js"))
const {
  CKEditorTranslationsPlugin,
} = require("@ckeditor/ckeditor5-dev-translations")

const prodConfig = Object.assign({}, config)
prodConfig.module.rules = [
  ...config.module.rules,
  {
    // this regex is necessary to explicitly exclude ckeditor stuff
    test: /static\/scss\/.+(\.css$|\.scss$)/,
    use: [
      {
        loader: MiniCssExtractPlugin.loader,
      },
      "css-loader?url=false",
      "postcss-loader",
      {
        loader: "sass-loader",
        options: {
          sassOptions: { quietDeps: true },
        },
      },
    ],
  },
]

module.exports = Object.assign(prodConfig, {
  context: __dirname,
  mode: "production",
  output: {
    path: path.resolve("./static/bundles/"),
    filename: "[name]-[chunkhash].js",
    chunkFilename: "[id]-[chunkhash].js",
    crossOriginLoading: "anonymous",
  },

  plugins: [
    new BundleTracker({
      filename: "webpack-stats.json",
      path: ".",
    }),
    new webpack.LoaderOptionsPlugin({
      minimize: true,
    }),
    new webpack.optimize.AggressiveMergingPlugin(),
    new MiniCssExtractPlugin({
      filename: "[name]-[contenthash].css",
    }),
    new CKEditorTranslationsPlugin({
      language: "en",
      addMainLanguageTranslationsToAllAssets: true,
    }),
    new webpack.DefinePlugin({
      RELEASE_YEAR: JSON.stringify(new Date().getUTCFullYear()),
    }),
  ],
  optimization: {
    minimize: true,
  },
  devtool: "source-map",
})
