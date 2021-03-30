import App from "./App"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"

describe("App", () => {
  let helper: IntegrationTestHelper, render: TestRenderer

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    render = helper.configureRenderer(App)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("App").exists()).toBeTruthy()
  })

  it("should render the site header", async () => {
    const { wrapper } = await render()
    const app = wrapper.find("App")
    const header = app.find("Header")
    expect(header.exists()).toBeTruthy()
  })
})
