import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import MarkdownEditor from './MarkdownEditor'

// issue with webpack SVG stuff
jest.mock("@ckeditor/ckeditor5-ui/src/icon/iconview.js")

describe('MarkdownEditor', () => {
  let helper: IntegrationTestHelper, render: TestRenderer, onChange

  beforeEach(() => {
    helper = new IntegrationTestHelper
    onChange = jest.fn()
    render = helper.configureRenderer(MarkdownEditor,
      { onChange, initialData: "" }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it('should render, attach onChange handler', async () => {
    const { wrapper } = await render(MarkdownEditor)
  })
})

