// Define globals we would usually get from Django
import ReactDOM from "react-dom"
import Adapter from "enzyme-adapter-react-16"
import Enzyme from "enzyme"
import failOnConsole from "jest-fail-on-console"
// Adds some dom-related matches to jest
import "@testing-library/jest-dom"

failOnConsole()

Enzyme.configure({ adapter: new Adapter() })

const _createSettings = (): typeof SETTINGS => ({
  reactGaDebug:    "",
  gaTrackingID:    "",
  public_path:     "",
  environment:     "",
  release_version: "0.0.0",
  sentry_dsn:      "",
  gdrive_enabled:  false,
  // @ts-expect-error Settings.user comes from django, but is left off SETTINGS type to encourage getting it from the store.
  user:            {
    username:      "example",
    name:          "Jane Doe",
    email:         "jane@example.com",
    canAddWebsite: true
  }
})

global.SETTINGS = _createSettings()
global._testing = true

beforeEach(() => {
  /**
   * We can't make ts aware that global.fetch is always a mock (the best we
   * could do is merge the mock + native declarations). So instead add a
   * separate mockFetch property and tell ts that it is always a mock.
   */
  global.mockFetch = jest.fn()
  global.fetch = global.mockFetch

  global.mockConfirm = jest.fn()
  global.confirm = global.mockConfirm
})

declare global {
  // eslint-disable-next-line no-var
  var mockFetch: jest.Mock<any, Parameters<typeof fetch>>,
    mockConfirm: jest.Mock<any, Parameters<typeof confirm>>
}

// cleanup after each test run
// eslint-disable-next-line mocha/no-top-level-hooks
afterEach(function() {
  /**
   * Clear all mock call counts between tests.
   * This does NOT clear mock implementations.
   * Mock implementations are always cleared between test files.
   */
  jest.clearAllMocks()
  jest.useRealTimers()
  const node = document.querySelector("#integration_test_div")
  if (node) {
    ReactDOM.unmountComponentAtNode(node)
  }
  document.body.innerHTML = ""
  global.SETTINGS = _createSettings()
  // @ts-ignore
  window.location = "http://fake/"
})
