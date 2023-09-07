const mockUseRouteMatch = jest.fn()

import React from "react"

import SiteContentListing, {
  repeatableTitle,
  singletonTitle,
} from "./SiteContentListing"

import IntegrationTestHelper, {
  TestRenderer,
} from "../util/integration_test_helper_old"
import {
  makeRepeatableConfigItem,
  makeSingletonsConfigItem,
  makeWebsiteConfigField,
  makeWebsiteDetail,
} from "../util/factories/websites"
import WebsiteContext from "../context/Website"

import {
  RepeatableConfigItem,
  SingletonsConfigItem,
  Website,
  WidgetVariant,
} from "../types/websites"

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: () => mockUseRouteMatch(),
}))

jest.mock("./RepeatableContentListing", () => ({
  __esModule: true,
  default: () => <div>MockComponent</div>,
}))

jest.mock("./SingletonsContentListing", () => ({
  __esModule: true,
  default: () => <div>MockComponent</div>,
}))

import MockRepeatable from "./RepeatableContentListing"
import MockSingletons from "./SingletonsContentListing"
import { DEFAULT_TITLE_FIELD } from "../lib/site_content"
import { assertNotNil } from "../test_util"

describe("SiteContentListing", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    render: TestRenderer,
    repeatableConfigItem: RepeatableConfigItem,
    singletonsConfigItem: SingletonsConfigItem

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    repeatableConfigItem = makeRepeatableConfigItem("repeatable_test_content")
    singletonsConfigItem = makeSingletonsConfigItem("singleton_test_content")
    website = makeWebsiteDetail()
    assertNotNil(website.starter)
    website.starter = {
      ...website.starter,
      config: {
        collections: [repeatableConfigItem, singletonsConfigItem],
      },
    }
    render = helper.configureRenderer((props) => (
      <WebsiteContext.Provider value={website}>
        <SiteContentListing {...props} />
      </WebsiteContext.Provider>
    ))
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("title funcs should be reasonable", () => {
    ;[
      ["input", "Input", "Inputs"],
      ["video_gallery", "Video Gallery", "Video Galleries"],
      ["sad_cat_house", "Sad Cat House", "Sad Cat Houses"],
    ].forEach(([contentType, singleExp, repeatExp]) => {
      expect(singletonTitle(contentType)).toBe(singleExp)
      expect(repeatableTitle(contentType)).toBe(repeatExp)
    })
  })

  const childCases = [
    { name: "repeatable", child: MockRepeatable },
    { name: "singleton", child: MockSingletons },
  ]

  it.each(childCases)(
    `renders $name with the correct props`,
    async ({ child }) => {
      const configItem =
        child === MockRepeatable ? repeatableConfigItem : singletonsConfigItem

      const params = { name: website.name, contentType: configItem.name }
      mockUseRouteMatch.mockImplementation(() => ({
        params,
      }))
      const { wrapper } = await render()

      const listing = wrapper.find(child)
      expect(listing.exists()).toBe(true)
      expect(listing.props()).toEqual({
        configItem,
      })
    },
  )

  it.each(childCases)("sets an appropriate title", async ({ child, name }) => {
    const configItem =
      child === MockRepeatable ? repeatableConfigItem : singletonsConfigItem

    const params = { name: website.name, contentType: configItem.name }
    mockUseRouteMatch.mockImplementation(() => ({
      params,
    }))
    const { wrapper } = await render()
    expect(wrapper.find("DocumentTitle").prop("title")).toBe(
      name === "repeatable"
        ? `OCW Studio | ${website.title} | Repeatable Test Contents`
        : `OCW Studio | ${website.title} | Singleton Test Content`,
    )
  })

  it("modifies config item fields before passing them on RepeatableContentListing", async () => {
    const params = {
      name: website.name,
      contentType: repeatableConfigItem.name,
    }
    mockUseRouteMatch.mockImplementation(() => ({
      params,
    }))

    const objectField = makeWebsiteConfigField({
      widget: WidgetVariant.Object,
      label: "myobject",
      fields: [
        makeWebsiteConfigField({
          widget: WidgetVariant.String,
          label: "mystring",
        }),
      ],
    })
    repeatableConfigItem.fields = [objectField]
    const { wrapper } = await render()
    const listing = wrapper.find(MockRepeatable)
    expect(listing.prop("configItem").fields).toStrictEqual([
      // Title field should be added by default
      DEFAULT_TITLE_FIELD,
      // Nested object field should be not renamed
      objectField,
    ])
  })
})
