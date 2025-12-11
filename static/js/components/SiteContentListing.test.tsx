const mockUseRouteMatch = jest.fn()

import React from "react"

import SiteContentListing, {
  repeatableTitle,
  singletonTitle,
} from "./SiteContentListing"

import { IntegrationTestHelper } from "../testing_utils"
import {
  makeRepeatableConfigItem,
  makeSingletonsConfigItem,
  makeWebsiteConfigField,
  makeWebsiteDetail,
} from "../util/factories/websites"

import {
  RepeatableConfigItem,
  SingletonsConfigItem,
  Website,
  WidgetVariant,
} from "../types/websites"
import { DEFAULT_TITLE_FIELD } from "../lib/site_content"
import { assertNotNil } from "../test_util"

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useRouteMatch: () => mockUseRouteMatch(),
}))

let capturedRepeatableProps: { configItem: RepeatableConfigItem } | null = null
let capturedSingletonsProps: { configItem: SingletonsConfigItem } | null = null

jest.mock("./RepeatableContentListing", () => ({
  __esModule: true,
  default: (props: { configItem: RepeatableConfigItem }) => {
    capturedRepeatableProps = props
    return <div data-testid="repeatable-content-listing">MockRepeatable</div>
  },
}))

jest.mock("./SingletonsContentListing", () => ({
  __esModule: true,
  default: (props: { configItem: SingletonsConfigItem }) => {
    capturedSingletonsProps = props
    return <div data-testid="singletons-content-listing">MockSingletons</div>
  },
}))

describe("SiteContentListing", () => {
  let helper: IntegrationTestHelper,
    website: Website,
    repeatableConfigItem: RepeatableConfigItem,
    singletonsConfigItem: SingletonsConfigItem

  beforeEach(() => {
    capturedRepeatableProps = null
    capturedSingletonsProps = null
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

  it("renders repeatable with the correct props", async () => {
    const params = {
      name: website.name,
      contentType: repeatableConfigItem.name,
    }
    mockUseRouteMatch.mockImplementation(() => ({
      params,
    }))
    helper.renderWithWebsite(<SiteContentListing />, website)

    expect(capturedRepeatableProps).not.toBeNull()
    expect(capturedRepeatableProps?.configItem).toEqual(repeatableConfigItem)
  })

  it("renders singleton with the correct props", async () => {
    const params = {
      name: website.name,
      contentType: singletonsConfigItem.name,
    }
    mockUseRouteMatch.mockImplementation(() => ({
      params,
    }))
    helper.renderWithWebsite(<SiteContentListing />, website)

    expect(capturedSingletonsProps).not.toBeNull()
    expect(capturedSingletonsProps?.configItem).toEqual(singletonsConfigItem)
  })

  it("sets an appropriate title for repeatable", async () => {
    const params = {
      name: website.name,
      contentType: repeatableConfigItem.name,
    }
    mockUseRouteMatch.mockImplementation(() => ({
      params,
    }))
    helper.renderWithWebsite(<SiteContentListing />, website)

    expect(document.title).toBe(
      `OCW Studio | ${website.title} | Repeatable Test Contents`,
    )
  })

  it("sets an appropriate title for singleton", async () => {
    const params = {
      name: website.name,
      contentType: singletonsConfigItem.name,
    }
    mockUseRouteMatch.mockImplementation(() => ({
      params,
    }))
    helper.renderWithWebsite(<SiteContentListing />, website)

    expect(document.title).toBe(
      `OCW Studio | ${website.title} | Singleton Test Content`,
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
    helper.renderWithWebsite(<SiteContentListing />, website)

    expect(capturedRepeatableProps).not.toBeNull()
    expect(capturedRepeatableProps?.configItem.fields).toStrictEqual([
      DEFAULT_TITLE_FIELD,
      objectField,
    ])
  })
})
