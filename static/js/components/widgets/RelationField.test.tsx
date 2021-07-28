import React from "react"
import { act } from "react-dom/test-utils"
import { when } from "jest-when"
import R from "ramda"

import RelationField from "./RelationField"
import { debouncedFetch } from "../../lib/api/util"
import WebsiteContext from "../../context/Website"

import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"

import {
  makeWebsiteContentDetail,
  makeWebsiteDetail
} from "../../util/factories/websites"
import { siteApiContentListingUrl } from "../../lib/urls"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../../constants"

import { Website, WebsiteContent } from "../../types/websites"
import { ReactWrapper } from "enzyme"

jest.mock("../../lib/api/util", () => ({
  ...jest.requireActual("../../lib/api/util"),
  debouncedFetch: jest.fn()
}))

describe("RelationField", () => {
  let website: Website,
    render: TestRenderer,
    helper: IntegrationTestHelper,
    onChange: () => void,
    contentListingItems: WebsiteContent[],
    fakeResponse: any

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
    contentListingItems = R.times(
      makeWebsiteContentDetail,
      WEBSITE_CONTENT_PAGE_SIZE
    )

    global.fetch = jest.fn()
    fakeResponse = {
      results:  contentListingItems,
      count:    contentListingItems.length,
      next:     null,
      previous: null
    }

    // @ts-ignore
    global.fetch.mockResolvedValue({ json: async () => fakeResponse })
  })

  afterEach(() => {
    helper.cleanup()
  })

  const asOption = (item: WebsiteContent) => ({
    value: item.text_id,
    label: item.title
  })

  //
  ;[true, false].forEach(hasContentContext => {
    ["other-site", ""].forEach(websiteNameProp => {
      it(`should render a SelectField with the expected options, ${
        hasContentContext ? "with" : "without"
      } contentContext, ${
        websiteNameProp ? "with" : "without"
      } a website prop`, async () => {
        // @ts-ignore
        when(global.fetch).mockResolvedValue({ json: async () => fakeResponse })
        const websiteName = websiteNameProp ? websiteNameProp : website.name
        const textIdsUrl = siteApiContentListingUrl
          .param({ name: websiteName })
          .query({
            detailed_list:   true,
            content_context: true,
            text_id:         contentListingItems.map(item => item.text_id),
            limit:           contentListingItems.length,
            type:            "page"
          })
          .toString()
        const contentContext = hasContentContext ?
          [makeWebsiteContentDetail()] :
          null
        const textIdsContentListingItems = [
          makeWebsiteContentDetail(),
          makeWebsiteContentDetail()
        ]
        when(global.fetch)
          .calledWith(textIdsUrl, { credentials: "include" })
          // @ts-ignore
          .mockResolvedValue({
            json: async () => ({
              results:  textIdsContentListingItems,
              count:    textIdsContentListingItems.length,
              next:     null,
              previous: null
            })
          })

        let wrapper: ReactWrapper
        await act(async () => {
          wrapper = (
            await render({
              value:   contentListingItems.map(item => item.text_id),
              website: websiteNameProp,
              contentContext
            })
          ).wrapper
        })
        // @ts-ignore
        wrapper.update()
        const combinedListing = [
          ...(contentContext ?? []),
          ...contentListingItems,
          ...(contentContext ? [] : textIdsContentListingItems)
        ]
        // @ts-ignore
        expect(wrapper.find("SelectField").prop("options")).toEqual(
          combinedListing.map(asOption)
        )
        // @ts-ignore
        expect(wrapper.find("SelectField").prop("defaultOptions")).toEqual(
          contentListingItems.map(asOption)
        )

        // there should be one or two initial fetches:
        // - a default 10 items to show when a user opens the dropdown
        // - text_ids for the case where contentContext is absent. If it is included in props, this fetch is skipped
        const defaultUrl = siteApiContentListingUrl
          .param({ name: websiteName })
          .query({
            detailed_list:   true,
            content_context: true,
            type:            "page"
          })
          .toString()
        // @ts-ignore
        expect(global.fetch).toHaveBeenCalledWith(defaultUrl, {
          credentials: "include"
        })

        if (hasContentContext) {
          expect(global.fetch).toHaveBeenCalledTimes(1)
          expect(global.fetch).not.toHaveBeenCalledWith(textIdsUrl, {
            credentials: "include"
          })
        } else {
          expect(global.fetch).toHaveBeenCalledTimes(2)
          expect(global.fetch).toHaveBeenCalledWith(textIdsUrl, {
            credentials: "include"
          })
        }
      })
    })
  })

  //
  ;[true, false].forEach(multiple => {
    it(`should pass the 'multiple===${multiple}' down to the SelectField`, async () => {
      let wrapper: ReactWrapper
      await act(async () => {
        wrapper = (await render({ multiple })).wrapper
      })
      // @ts-ignore
      expect(wrapper.find("SelectField").prop("multiple")).toBe(multiple)
    })
  })

  it("should pass a value down to the SelectField", async () => {
    let wrapper: ReactWrapper
    await act(async () => {
      wrapper = (await render({ value: "foobar" })).wrapper
    })
    // @ts-ignore
    expect(wrapper.find("SelectField").prop("value")).toBe("foobar")
  })

  it("should filter results", async () => {
    contentListingItems[0].metadata!.testfield = "testvalue"
    let wrapper: ReactWrapper
    await act(async () => {
      wrapper = (
        await render({
          filter: {
            field:       "testfield",
            filter_type: "equals",
            value:       "testvalue"
          }
        })
      ).wrapper
    })
    // @ts-ignore
    wrapper.update()
    // @ts-ignore
    expect(wrapper.find("SelectField").prop("options")).toEqual([
      {
        label: contentListingItems[0].title,
        value: contentListingItems[0].text_id
      }
    ])
  })

  it("should accept an onChange prop, which gets passed to the child select component", async () => {
    const onChangeStub = jest.fn()
    const fakeEvent = { target: { value: "abc" } }
    await act(async () => {
      const { wrapper } = await render({
        onChange: onChangeStub
      })
      const select = wrapper.find("SelectField")
      // @ts-ignore
      select.prop("onChange")(fakeEvent)
    })
    expect(onChangeStub).toBeCalledTimes(1)
    expect(onChangeStub).toBeCalledWith(fakeEvent)
  })

  it("should accept a setFieldValue prop, which is called when the select field changes", async () => {
    const setFieldValueStub = jest.fn()
    await act(async () => {
      const { wrapper } = await render({
        name:          "nested.field",
        setFieldValue: setFieldValueStub,
        onChange:      null
      })
      const select = wrapper.find("SelectField")
      const fakeEvent = { target: { value: "abc" } }
      // @ts-ignore
      select.prop("onChange")(fakeEvent)
    })
    expect(setFieldValueStub).toBeCalledTimes(1)
    expect(setFieldValueStub).toBeCalledWith("nested", {
      website: website.name,
      content: "abc"
    })
  })

  it("should have a loadOptions prop which triggers a debounced fetch of results", async () => {
    let wrapper: ReactWrapper, loadOptionsResponse
    await act(async () => {
      wrapper = (await render()).wrapper
    })
    // @ts-ignore
    wrapper.update()
    // @ts-ignore
    const loadOptions = wrapper.find("SelectField").prop("loadOptions")
    const searchString1 = "searchstring1",
      searchString2 = "searchstring2"

    // @ts-ignore
    debouncedFetch.mockResolvedValue({ json: async () => fakeResponse })

    await act(async () => {
      loadOptionsResponse = await Promise.all([
        // @ts-ignore
        loadOptions(searchString1),
        // @ts-ignore
        loadOptions(searchString2)
      ])
    })

    const urlForSearch = (search: string) =>
      siteApiContentListingUrl
        .query({
          detailed_list:   true,
          content_context: true,
          search:          search,
          type:            "page"
        })
        .param({ name: website.name })
        .toString()
    expect(debouncedFetch).toBeCalledTimes(2)
    expect(debouncedFetch).toBeCalledWith(
      "relationfield",
      300,
      urlForSearch(searchString1),
      { credentials: "include" }
    )
    expect(debouncedFetch).toBeCalledWith(
      "relationfield",
      300,
      urlForSearch(searchString2),
      { credentials: "include" }
    )
    expect(loadOptionsResponse).toStrictEqual([
      fakeResponse.results.map(asOption),
      fakeResponse.results.map(asOption)
    ])
  })

  //
  ;[true, false].forEach(valueIsArray => {
    it(`should omit items listed by valuesToOmit, except those already selected, when value ${
      valueIsArray ? "is" : "is not"
    } an array`, async () => {
      let wrapper: ReactWrapper, loadOptionsResponse
      const valuesToOmit = new Set([
        contentListingItems[0].text_id,
        contentListingItems[2].text_id,
        contentListingItems[3].text_id
      ])
      const value = valueIsArray ?
        [contentListingItems[0].text_id, contentListingItems[1].text_id] :
        contentListingItems[0].text_id
      const expectedResults = fakeResponse.results.filter(
        (_: any, idx: number) => idx !== 2 && idx !== 3
      )
      const expectedOptions = expectedResults.map(asOption)

      await act(async () => {
        wrapper = (await render({ valuesToOmit, value })).wrapper
      })
      // @ts-ignore
      wrapper.update()
      // @ts-ignore
      const loadOptions = wrapper.find("SelectField").prop("loadOptions")

      // @ts-ignore
      debouncedFetch.mockResolvedValue({ json: async () => fakeResponse })

      await act(async () => {
        // @ts-ignore
        loadOptionsResponse = await loadOptions()
      })

      expect(loadOptionsResponse).toStrictEqual(expectedOptions)
    })
  })
})
