const mockUseRouteMatch = jest.fn()

import React from "react"

import SiteContentListing from "./SiteContentListing"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeRepeatableConfigItem,
  makeSingletonsConfigItem,
  makeWebsiteConfigField,
  makeWebsiteDetail
} from "../util/factories/websites"

import {
  RepeatableConfigItem,
  SingletonsConfigItem,
  Website,
  WidgetVariant
} from "../types/websites"

jest.mock("react-router-dom", () => ({
  // @ts-ignore
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: mockUseRouteMatch
}))

jest.mock("./RepeatableContentListing", () => ({
  __esModule: true,
  default:    () => <div>MockComponent</div>
}))
jest.mock("./SingletonsContentListing", () => ({
  __esModule: true,
  default:    () => <div>MockComponent</div>
}))
import MockRepeatable from "./RepeatableContentListing"
import MockSingletons from "./SingletonsContentListing"
import { DEFAULT_TITLE_FIELD } from "../lib/site_content"

describe("SiteContentListing", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    render: TestRenderer,
    repeatableConfigItem: RepeatableConfigItem,
    singletonsConfigItem: SingletonsConfigItem

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    repeatableConfigItem = makeRepeatableConfigItem()
    singletonsConfigItem = makeSingletonsConfigItem()
    website = makeWebsiteDetail()
    // @ts-ignore
    website.starter = {
      ...website.starter,
      config: {
        collections: [repeatableConfigItem, singletonsConfigItem]
      }
    }
    render = helper.configureRenderer(
      SiteContentListing,
      {
        location: {
          search: ""
        }
      },
      {
        entities: {
          websiteDetails: { [website.name]: website }
        },
        queries: {}
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  //
  ;[MockRepeatable, MockSingletons].forEach(child => {
    it(`renders listing components with the correct props`, async () => {
      let configItem

      if (child === MockRepeatable) {
        configItem = repeatableConfigItem
      } else {
        configItem = singletonsConfigItem
      }

      // @ts-ignore
      const params = { name: website.name, contenttype: configItem.name }
      mockUseRouteMatch.mockImplementation(() => ({
        params
      }))
      const { wrapper } = await render()
      const listing = wrapper.find(child)
      expect(listing.exists()).toBe(true)
      expect(listing.props()).toEqual({
        configItem
      })
    })
  })

  it("modifies config item fields before passing them on RepeatableContentListing", async () => {
    const params = {
      name:        website.name,
      contenttype: repeatableConfigItem.name
    }
    mockUseRouteMatch.mockImplementation(() => ({
      params
    }))

    const objectField = makeWebsiteConfigField({
      widget: WidgetVariant.Object,
      label:  "myobject",
      fields: [
        makeWebsiteConfigField({
          widget: WidgetVariant.String,
          label:  "mystring"
        })
      ]
    })
    repeatableConfigItem.fields = [objectField]
    const { wrapper } = await render()
    const listing = wrapper.find(MockRepeatable)
    expect(listing.prop("configItem").fields).toStrictEqual([
      // Title field should be added by default
      DEFAULT_TITLE_FIELD,
      // Nested object field should be not renamed
      objectField
    ])
  })
})
