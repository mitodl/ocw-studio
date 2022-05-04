import React from "react"
import { act } from "react-dom/test-utils"
import R from "ramda"

import RelationField from "./RelationField"
import { debouncedFetch } from "../../lib/api/util"
import WebsiteContext from "../../context/Website"
import { Option } from "./SelectField"

import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper_old"

import {
  makeWebsiteContentDetail,
  makeWebsiteDetail,
  makeWebsites
} from "../../util/factories/websites"
import { siteApiContentListingUrl } from "../../lib/urls"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../../constants"

import {
  RelationFilterVariant,
  Website,
  WebsiteContent
} from "../../types/websites"
import { ReactWrapper } from "enzyme"
import { FormError } from "../forms/FormError"
import {
  formatWebsiteOptions,
  useWebsiteSelectOptions
} from "../../hooks/websites"
import SortableSelect from "./SortableSelect"

jest.mock("../../lib/api/util", () => ({
  ...jest.requireActual("../../lib/api/util"),
  debouncedFetch: jest.fn()
}))

jest.mock("../../hooks/websites", () => ({
  ...jest.requireActual("../../hooks/websites"),
  useWebsiteSelectOptions: jest.fn()
}))

describe("RelationField", () => {
  let website: Website,
    render: TestRenderer,
    _render: TestRenderer,
    helper: IntegrationTestHelper,
    onChange: jest.Mock,
    contentListingItems: WebsiteContent[],
    fakeResponse: any,
    websites: Website[]

  beforeEach(() => {
    website = makeWebsiteDetail()
    helper = new IntegrationTestHelper()
    onChange = jest.fn()
    _render = helper.configureRenderer(
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

    // @ts-ignore
    render = async (props = {}) => {
      let _wrapper, _store
      await act(async () => {
        // @ts-ignore
        const { wrapper, store } = await _render(props)
        // @ts-ignore
        _wrapper = wrapper
        // @ts-ignore
        _store = store
      })
      return {
        // @ts-ignore
        wrapper: _wrapper,
        // @ts-ignore
        store:   _store
      }
    }

    contentListingItems = R.times(
      () => ({
        ...makeWebsiteContentDetail(),
        metadata: {
          resourcetype: "Image"
        }
      }),
      WEBSITE_CONTENT_PAGE_SIZE
    )

    fakeResponse = {
      results:  contentListingItems,
      count:    contentListingItems.length,
      next:     null,
      previous: null
    }

    global.mockFetch.mockResolvedValue({ json: async () => fakeResponse })
    // @ts-ignore
    debouncedFetch.mockResolvedValue({ json: async () => fakeResponse })

    websites = makeWebsites()
    // @ts-ignore
    useWebsiteSelectOptions.mockReturnValue({
      options:     formatWebsiteOptions(websites, "name"),
      loadOptions: jest.fn()
    })
  })

  afterEach(() => {
    helper.cleanup()

    // @ts-ignore
    debouncedFetch.mockClear()
    global.mockFetch.mockClear()
    // @ts-ignore
    useWebsiteSelectOptions.mockReset()
  })

  const asOption = (item: WebsiteContent) => ({
    value: item.text_id,
    label: item.title
  })

  //
  ;[true, false].forEach(hasContentContext => {
    [true, false].forEach(withResourcetypeFilter => {
      ["other-site", ""].forEach(websiteNameProp => {
        it(`should render a SelectField with the expected options, ${
          hasContentContext ? "with" : "without"
        } contentContext, ${
          websiteNameProp ? "with" : "without"
        } a website prop, ${
          withResourcetypeFilter ? "with" : "without"
        } a resourcetype filter`, async () => {
          const websiteName = websiteNameProp ? websiteNameProp : website.name
          const contentContext = hasContentContext ?
            [makeWebsiteContentDetail()] :
            null

          const { wrapper } = await render({
            value:   contentListingItems.map(item => item.text_id),
            website: websiteNameProp,
            contentContext,
            filter:  withResourcetypeFilter ?
              {
                filter_type: RelationFilterVariant.Equals,
                field:       "resourcetype",
                value:       "Image"
              } :
              null
          })
          wrapper.update()
          const combinedListing = [
            ...(contentContext ?? []),
            ...contentListingItems
          ]
          expect(wrapper.find("SelectField").prop("options")).toEqual(
            combinedListing.map(asOption)
          )
          expect(wrapper.find("SelectField").prop("defaultOptions")).toEqual(
            contentListingItems.map(asOption)
          )

          // there should be one or two initial fetches:
          //
          // - a default 10 items to show when a user opens the dropdown
          // - text_ids for the case where contentContext is absent. If it is
          //   included in props, this fetch is skipped
          const defaultUrl = siteApiContentListingUrl
            .param({ name: websiteName })
            .query({
              detailed_list:   true,
              content_context: true,
              type:            "page",
              ...(withResourcetypeFilter ? { resourcetype: "Image" } : {})
            })
            .toString()
          expect(global.fetch).toHaveBeenCalledTimes(1)
          expect(global.fetch).toHaveBeenCalledWith(defaultUrl, {
            credentials: "include"
          })
        })
      })
    })
  })

  describe("cross_site option", () => {
    it("should present default options for websites", async () => {
      const { wrapper } = await render({ cross_site: true, value: [] })
      expect(
        wrapper
          .find("SelectField")
          .at(0)
          .prop("defaultOptions")
      ).toEqual(formatWebsiteOptions(websites, "name"))
    })

    it.each([true, false])(
      "should not filter on published if cross_site is not set",
      async isCrossSite => {
        await render({ cross_site: isCrossSite, value: [] })
        expect(global.fetch).toHaveBeenCalledWith(
          siteApiContentListingUrl
            .query({
              detailed_list:   true,
              content_context: true,
              type:            "page",
              ...(isCrossSite ? { published: true } : {})
            })
            .param({ name: website.name })
            .toString(),
          { credentials: "include" }
        )
      }
    )

    it("should let the user pick a website and then content within that website", async () => {
      const { wrapper } = await render({ cross_site: true, value: [] })
      await act(async () => {
        // @ts-ignore
        wrapper
          .find("SelectField")
          .at(0)
          .prop("onChange")({
          // @ts-ignore
            target: { value: "new-uuid" }
          })
        wrapper.update()
      })

      // website is now set, so a request is issued for content within
      // that website
      expect(global.fetch).toHaveBeenCalledWith(
        siteApiContentListingUrl
          .query({
            detailed_list:   true,
            content_context: true,
            type:            "page",
            published:       true
          })
          .param({
            name: "new-uuid"
          })
          .toString(),
        { credentials: "include" }
      )

      // UI now shows content
      expect(
        // @ts-ignore
        wrapper
          .find("SelectField")
          .at(1)
          .prop("options")
      ).toEqual(
        contentListingItems.map(item => ({
          value: item.text_id,
          label: item.title
        }))
      )

      await act(async () => {
        wrapper.find(SortableSelect).prop("onChange")([
          contentListingItems[0].text_id
        ])
        wrapper.update()
      })

      // this expect call is a regression test for the fix for
      // https://github.com/mitodl/ocw-studio/issues/940
      expect(onChange.mock.calls[0][0]).toEqual({
        target: {
          name:  "relation_field",
          value: {
            website: website.name,
            content: [[contentListingItems[0].text_id, website.name]]
          }
        }
      })
    })
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
    contentListingItems[0].metadata!.testfield = "testvalue"
    const { wrapper } = await render({
      filter: {
        field:       "testfield",
        filter_type: "equals",
        value:       "testvalue"
      }
    })
    wrapper.update()
    expect(wrapper.find("SelectField").prop("options")).toEqual([
      {
        label: contentListingItems[0].title,
        value: contentListingItems[0].text_id
      }
    ])
  })

  //
  ;[
    ["name", "name"],
    ["name.content", "name"]
  ].forEach(([name, expectedName]) => {
    it(`should accept an onChange prop with name=${name}, which gets modified then passed to the child select component`, async () => {
      const onChangeStub = jest.fn()
      const { wrapper } = await render({
        onChange: onChangeStub,
        name
      })
      const select = wrapper.find("SelectField")
      const numbers = ["one", "two", "three"]
      const fakeEvent = { target: { value: numbers, name } }
      await act(async () => {
        // @ts-ignore
        select.prop("onChange")(fakeEvent)
      })
      expect(onChangeStub).toBeCalledWith({
        target: {
          name:  expectedName,
          value: {
            website: website.name,
            content: numbers
          }
        }
      })
    })
  })

  //
  ;[true, false].forEach(withResourcetypeFilter => {
    it(`should have a loadOptions prop which triggers a debounced fetch of results, ${
      withResourcetypeFilter ? "with" : "without"
    } a resourcetype filter`, async () => {
      let loadOptionsResponse
      const { wrapper } = await render({
        filter: withResourcetypeFilter ?
          {
            filter_type: RelationFilterVariant.Equals,
            field:       "resourcetype",
            value:       "Image"
          } :
          null
      })
      wrapper.update()
      const loadOptions: (input: string) => Promise<Option[]> = wrapper
        .find("SelectField")
        .prop("loadOptions")
      const searchString1 = "searchstring1",
        searchString2 = "searchstring2"

      await act(async () => {
        loadOptionsResponse = await Promise.all([
          loadOptions(searchString1),
          loadOptions(searchString2)
        ])
      })

      const urlForSearch = (search: string) =>
        siteApiContentListingUrl
          .query({
            detailed_list:   true,
            content_context: true,
            search:          search,
            type:            "page",
            ...(withResourcetypeFilter ? { resourcetype: "Image" } : {})
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

      await act(async () => {
        // @ts-ignore
        loadOptionsResponse = await loadOptions()
      })

      expect(loadOptionsResponse).toStrictEqual(expectedOptions)
    })
  })

  it("should display an error message ", async () => {
    global.mockFetch.mockClear()
    const fakeResponse = {
      results:  undefined,
      count:    0,
      next:     null,
      previous: null
    }
    global.mockFetch.mockResolvedValue({ json: async () => fakeResponse })
    const { wrapper } = await render()
    wrapper.update()
    const error = wrapper.find(FormError)
    expect(error.text()).toBe("Unable to fetch entries for this field.")
  })

  describe("sortable UI", () => {
    it("should show a sortable UI when the prop is passed", async () => {
      const value = contentListingItems.map(item => item.text_id)
      const { wrapper } = await render({
        multiple: true,
        sortable: true,
        value
      })
      const sortableSelect = wrapper.find("SortableSelect")
      expect(sortableSelect.exists()).toBeTruthy()
      expect(sortableSelect.prop("value")).toStrictEqual(
        value.map(id => ({
          id,
          title: id
        }))
      )
    })

    it("should disable already-selected options", async () => {
      const value = contentListingItems.slice(3).map(item => item.text_id)
      const options = contentListingItems.map(item => ({
        value: item.text_id,
        label: item.title ?? "title"
      }))
      const { wrapper } = await render({
        multiple: true,
        sortable: true,
        value
      })

      const isOptionEnabled = wrapper
        .find(SortableSelect)
        .prop("isOptionDisabled")!
      expect(isOptionEnabled).toBeDefined()
      const expected = [false, false, false, ...Array(7).fill(true)]
      expect(options.map(isOptionEnabled)).toEqual(expected)
    })
  })
})
