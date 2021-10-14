import React from "react"
import { act } from "react-dom/test-utils"
import R from "ramda"
import sinon, { SinonStub } from "sinon"

import RelationField from "./RelationField"
import { debouncedFetch } from "../../lib/api/util"
import WebsiteContext from "../../context/Website"
import { Option } from "./SelectField"

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
import { DndContext } from "@dnd-kit/core"

jest.mock("../../lib/api/util", () => ({
  ...jest.requireActual("../../lib/api/util"),
  debouncedFetch: jest.fn()
}))

describe("RelationField", () => {
  let website: Website,
    render: TestRenderer,
    _render: TestRenderer,
    helper: IntegrationTestHelper,
    onChange: SinonStub,
    contentListingItems: WebsiteContent[],
    fakeResponse: any

  beforeEach(() => {
    website = makeWebsiteDetail()
    helper = new IntegrationTestHelper()
    onChange = helper.sandbox.stub()
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
        const websiteName = websiteNameProp ? websiteNameProp : website.name
        const contentContext = hasContentContext ?
          [makeWebsiteContentDetail()] :
          null

        const { wrapper } = await render({
          value:   contentListingItems.map(item => item.text_id),
          website: websiteNameProp,
          contentContext
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
            type:            "page"
          })
          .toString()
        expect(global.fetch).toHaveBeenCalledTimes(1)
        expect(global.fetch).toHaveBeenCalledWith(defaultUrl, {
          credentials: "include"
        })
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

  it("should have a loadOptions prop which triggers a debounced fetch of results", async () => {
    let loadOptionsResponse
    const { wrapper } = await render()
    wrapper.update()
    const loadOptions: (input: string) => Promise<Option[]> = wrapper
      .find("SelectField")
      .prop("loadOptions")
    const searchString1 = "searchstring1",
      searchString2 = "searchstring2"

    // @ts-ignore
    debouncedFetch.mockResolvedValue({ json: async () => fakeResponse })

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

  describe("sortable UI", () => {
    it("should show a sortable UI when the prop is passed", async () => {
      const value = contentListingItems.map(item => item.text_id)
      const { wrapper } = await render({
        multiple: true,
        sortable: true,
        value
      })
      expect(wrapper.find("SortableContext").exists()).toBeTruthy()
      expect(
        wrapper
          .find("SortableContext SortableItem")
          .map(item => item.prop("id"))
      ).toStrictEqual(value)
    })

    it("should allow adding another element", async () => {
      const { wrapper } = await render({
        multiple: true,
        sortable: true,
        value:    []
      })
      await act(async () => {
        // @ts-ignore
        wrapper.find("SelectField").prop("onChange")({
          // @ts-ignore
          target: { value: "new-uuid" }
        })
      })
      wrapper.update()
      wrapper.find(".cyan-button").simulate("click")
      sinon.assert.calledWith(onChange, {
        target: {
          name:  "relation_field",
          value: { website: website.name, content: ["new-uuid"] }
        }
      })
      expect(wrapper.find("SelectField").prop("value")).toBeUndefined()
    })

    it("should let you drag and drop items to reorder", async () => {
      const value = ["uuid-1", "uuid-2", "uuid-3"]
      const { wrapper } = await render({
        multiple: true,
        sortable: true,
        value
      })

      act(() => {
        wrapper.find(DndContext)!.prop("onDragEnd")!({
          active: { id: "uuid-3" },
          over:   { id: "uuid-1" }
        } as any)
      })
      sinon.assert.calledWith(onChange, {
        target: {
          name:  "relation_field",
          value: {
            website: website.name,
            content: ["uuid-3", "uuid-1", "uuid-2"]
          }
        }
      })
    })
  })
})
