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

  it("should render", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("App").exists()).toBeTruthy()
  })
})
