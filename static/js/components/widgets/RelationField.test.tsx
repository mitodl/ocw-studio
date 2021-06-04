import React from "react"
import { SinonStub } from "sinon"

import RelationField from "./RelationField"
import WebsiteContext from "../../context/Website"

import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"

import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import { siteApiContentListingUrl, siteApiDetailUrl } from "../../lib/urls"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../../constants"

import { Website, WebsiteContent } from "../../types/websites"
import R from "ramda"

describe("RelationField", () => {
  let website: Website,
    otherWebsite: Website,
    render: TestRenderer,
    helper: IntegrationTestHelper,
    onChange: SinonStub,
    contentListingItemsPages: WebsiteContent[][]

  beforeEach(() => {
    website = makeWebsiteDetail()
    otherWebsite = makeWebsiteDetail()
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
      R.times(makeWebsiteContentDetail, WEBSITE_CONTENT_PAGE_SIZE),
      R.times(makeWebsiteContentDetail, WEBSITE_CONTENT_PAGE_SIZE)
    ]
    ;[website, otherWebsite].forEach(website => {
      helper.handleRequestStub
        .withArgs(
          siteApiContentListingUrl
            .param({ name: website.name })
            .query({ type: "page", offset: 0, detailed_list: true })
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
            .query({
              type:          "page",
              offset:        WEBSITE_CONTENT_PAGE_SIZE,
              detailed_list: true
            })
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

  it("should filter results", async () => {
    contentListingItemsPages[0][0].metadata!.testfield = "testvalue"
    const { wrapper } = await render({
      filter: {
        field:       "testfield",
        filter_type: "equals",
        value:       "testvalue"
      }
    })
    expect(wrapper.find("SelectField").prop("options")).toEqual([
      {
        label: contentListingItemsPages[0][0].title,
        value: contentListingItemsPages[0][0].text_id
      }
    ])
  })

  describe("manually-set website parameter", () => {
    beforeEach(() => {
      helper.handleRequestStub
        .withArgs(
          siteApiDetailUrl.param({ name: otherWebsite.name }).toString()
        )
        .returns({
          status: 200,
          body:   otherWebsite
        })
    })

    it("should support setting a 'website' parameter, fetching and using that website", async () => {
      const { wrapper } = await render({
        website: otherWebsite.name
      })

      expect(
        helper.handleRequestStub.calledWith(
          siteApiDetailUrl.param({ name: otherWebsite.name }).toString()
        )
      ).toBeTruthy()

      expect(wrapper.find("SelectField").prop("options")).toEqual(
        contentListingItemsPages.flat().map(entry => ({
          label: entry.title,
          value: entry.text_id
        }))
      )
    })
  })
})
