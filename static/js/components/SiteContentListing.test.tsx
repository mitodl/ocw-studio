const mockUseRouteMatch = jest.fn()

import React from "react"

import SiteContentListing from "./SiteContentListing"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import {
  makeRepeatableConfigItem,
  makeSingletonsConfigItem,
  makeWebsiteDetail
} from "../util/factories/websites"

import {
  RepeatableConfigItem,
  SingletonsConfigItem,
  Website
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

describe("SiteContentListing", () => {
  const repeatableConfigItem: RepeatableConfigItem = makeRepeatableConfigItem(),
    singletonsConfigItem: SingletonsConfigItem = makeSingletonsConfigItem()
  let helper: IntegrationTestHelper, website: Website, render: TestRenderer

  beforeEach(() => {
    helper = new IntegrationTestHelper()
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
  ;[
    [repeatableConfigItem, MockRepeatable, "RepeatableContentListing"],
    [singletonsConfigItem, MockSingletons, "SingletonsContentListing"]
  ].forEach(([configItem, expChildComponent, desc]) => {
    it(`renders a ${desc} component with the correct props`, async () => {
      // @ts-ignore
      const params = { name: website.name, contenttype: configItem.name }
      mockUseRouteMatch.mockImplementation(() => ({
        params
      }))

      const { wrapper } = await render()
      // @ts-ignore
      const listing = wrapper.find(expChildComponent)
      expect(listing.exists()).toBe(true)
      expect(listing.props()).toEqual({
        website:    website,
        configItem: configItem
      })
    })
  })
})
