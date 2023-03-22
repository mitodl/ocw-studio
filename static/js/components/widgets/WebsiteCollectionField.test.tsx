import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper_old"
import WebsiteCollectionField from "./WebsiteCollectionField"

import * as websiteHooks from "../../hooks/websites"
import { Website } from "../../types/websites"
import { makeWebsites } from "../../util/factories/websites"
import { triggerSortableSelect } from "./test_util"
import { Option } from "./SelectField"
import SortableSelect from "./SortableSelect"

jest.mock("../../hooks/websites", () => ({
  ...jest.requireActual("../../hooks/websites"),
  useWebsiteSelectOptions: jest.fn()
}))
const useWebsiteSelectOptions = jest.mocked(
  websiteHooks.useWebsiteSelectOptions
)

describe("WebsiteCollectionField", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    onChange: jest.Mock,
    websites: Website[],
    websiteOptions: Option[]

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    onChange = jest.fn()
    render = helper.configureRenderer(WebsiteCollectionField, {
      onChange,
      name:  "test-site-collection",
      value: []
    })
    websites = makeWebsites()
    websiteOptions = websiteHooks.formatWebsiteOptions(websites, "name")
    useWebsiteSelectOptions.mockReturnValue({
      options:     websiteOptions,
      loadOptions: jest.fn()
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should pass published=true to the useWebsiteSelectOptions", async () => {
    await render()
    expect(useWebsiteSelectOptions).toHaveBeenCalledWith("url_path", true)
  })

  it("should pass things down to SortableSelect", async () => {
    const value = websites.map(website => ({
      id:    website.url_path,
      title: website.title
    }))

    const { wrapper } = await render({
      value
    })
    const sortableSelect = wrapper.find(SortableSelect)
    expect(sortableSelect.prop("value")).toStrictEqual(value)
    expect(sortableSelect.prop("options")).toStrictEqual(websiteOptions)
    expect(sortableSelect.prop("defaultOptions")).toStrictEqual(websiteOptions)
  })

  it("should let the user add a website, with UUID and title", async () => {
    const { wrapper } = await render()
    wrapper.update()
    await triggerSortableSelect(wrapper, websites[0].name)
    expect(onChange).toHaveBeenCalledWith({
      target: {
        name:  "test-site-collection",
        value: [
          {
            id:    websites[0].name,
            title: websites[0].title
          }
        ]
      }
    })
  })

  it("should disable website options that have already been selected", async () => {
    expect(websites.length).toBeGreaterThan(2)
    const value = websites.slice(2).map(website => ({
      id:    website.name,
      title: website.title
    }))
    const { wrapper } = await render({ value })
    const isOptionEnabled = wrapper
      .find(SortableSelect)
      .prop("isOptionDisabled")!
    expect(isOptionEnabled).toBeDefined()
    const expected = [false, false, ...Array(8).fill(true)]
    expect(websiteOptions.map(isOptionEnabled)).toEqual(expected)
  })
})
