import React from "react"
import { SinonStub } from "sinon"

import RelationField from "./RelationField"
import WebsiteContext from "../../context/Website"

import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"

import {
  makeWebsiteContentListItem,
  makeWebsiteDetail
} from "../../util/factories/websites"
import { siteApiContentListingUrl } from "../../lib/urls"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../../constants"

import { Website, WebsiteContentListItem } from "../../types/websites"
import R from "ramda"

describe("RelationField", () => {
  let website: Website,
    render: TestRenderer,
    helper: IntegrationTestHelper,
    onChange: SinonStub,
    contentListingItemsPages: WebsiteContentListItem[][]

  beforeEach(() => {
    website = makeWebsiteDetail()
    helper = new IntegrationTestHelper()
    onChange = helper.sandbox.stub()
    render = helper.configureRenderer(
      props => (
        <WebsiteContext.Provider value={website}>
          <RelationField {...props} />
        </WebsiteContext.Provider>
      ),
      {
        collection:    "page",
        display_field: "title",
        name:          "relation_field",
        multiple:      true,
        onChange
      }
    )
    contentListingItemsPages = [
      R.times(makeWebsiteContentListItem, WEBSITE_CONTENT_PAGE_SIZE),
      R.times(makeWebsiteContentListItem, WEBSITE_CONTENT_PAGE_SIZE)
    ]
    helper.handleRequestStub
      .withArgs(
        siteApiContentListingUrl
          .param({ name: website.name })
          .query({ type: "page", offset: 0 })
          .toString(),
        "GET"
      )
      .returns({
        status: 200,
        body:   {
          results:  contentListingItemsPages[0],
          count:    contentListingItemsPages.flat().length,
          next:     null,
          previous: null
        }
      })
    helper.handleRequestStub
      .withArgs(
        siteApiContentListingUrl
          .param({ name: website.name })
          .query({ type: "page", offset: WEBSITE_CONTENT_PAGE_SIZE })
          .toString(),
        "GET"
      )
      .returns({
        status: 200,
        body:   {
          results:  contentListingItemsPages[1],
          count:    contentListingItemsPages.flat().length,
          next:     null,
          previous: null
        }
      })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should render a SelectField with the expected options, hitting the API multiple times as needed", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("SelectField").prop("options")).toEqual(
      contentListingItemsPages.flat().map(item => ({
        label: item.title,
        value: item.text_id
      }))
    )
  })

  //
  ;[true, false].forEach(multiple => {
    it(`should pass the 'multiple===${multiple}' down to the SelectField`, async () => {
      const { wrapper } = await render({ multiple })
      expect(wrapper.find("SelectField").prop("multiple")).toBe(multiple)
    })
  })

  it("should pass a value down to the SelectField", async () => {
    const { wrapper } = await render({ value: "foobar" })
    expect(wrapper.find("SelectField").prop("value")).toBe("foobar")
  })

  it("should pass the onChange handler down to the SelectField", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("SelectField").prop("onChange")).toBe(onChange)
  })
})
