// Define globals we would usually get from Django
import ReactDOM from "react-dom"
import Adapter from "enzyme-adapter-react-16"
import Enzyme from "enzyme"

Enzyme.configure({ adapter: new Adapter() })

const _createSettings = (): SETTINGS => ({
  reactGaDebug:    "",
  gaTrackingID:    "",
  public_path:     "",
  environment:     "",
  release_version: "0.0.0",
  sentry_dsn:      ""
})

global.SETTINGS = _createSettings()
global._testing = true

// cleanup after each test run
// eslint-disable-next-line mocha/no-top-level-hooks
afterEach(function() {
  const node = document.querySelector("#integration_test_div")
  if (node) {
    ReactDOM.unmountComponentAtNode(node)
  }
  document.body.innerHTML = ""
  global.SETTINGS = _createSettings()
  // @ts-ignore
  window.location = "http://fake/"
})
