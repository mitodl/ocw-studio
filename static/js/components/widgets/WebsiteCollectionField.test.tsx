import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import WebsiteCollectionField from "./WebsiteCollectionField"

import { formatOptions, useWebsiteSelectOptions } from "../../hooks/websites"
import { Website } from "../../types/websites"
import { makeWebsiteListing } from "../../util/factories/websites"
import { triggerSortableSelect } from "./test_util"
import { Option } from "./SelectField"

jest.mock("../../hooks/websites", () => ({
  ...jest.requireActual("../../hooks/websites"),
  useWebsiteSelectOptions: jest.fn()
}))

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
    websites = makeWebsiteListing()
    websiteOptions = formatOptions(websites, "uuid")
    // @ts-ignore
    useWebsiteSelectOptions.mockReturnValue({
      options:     websiteOptions,
      loadOptions: jest.fn()
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should pass things down to SortableSelect", async () => {
    const value = websites.map(website => ({
      id:    website.uuid,
      title: website.title
    }))

    const { wrapper } = await render({
      value
    })
    const sortableSelect = wrapper.find("SortableSelect")
    expect(sortableSelect.prop("value")).toStrictEqual(value)
    expect(sortableSelect.prop("options")).toStrictEqual(websiteOptions)
    expect(sortableSelect.prop("defaultOptions")).toStrictEqual(websiteOptions)
  })

  it("should let the user add a website, with UUID and title", async () => {
    const { wrapper } = await render()
    wrapper.update()
    await triggerSortableSelect(wrapper, [websites[0].uuid])
    expect(onChange).toBeCalledWith({
      target: {
        name:  "test-site-collection",
        value: [
          {
            id:    websites[0].uuid,
            title: websites[0].title
          }
        ]
      }
    })
  })
})
