import React from "react"
import { screen, waitFor } from "@testing-library/react"
import { act } from "@testing-library/react"
import R from "ramda"

import RelationField from "./RelationField"
import * as apiUtil from "../../lib/api/util"
import WebsiteContext from "../../context/Website"
import { Option } from "./SelectField"

import { IntegrationTestHelper } from "../../testing_utils"

import {
  makeWebsiteContentDetail,
  makeWebsiteDetail,
  makeWebsites,
} from "../../util/factories/websites"
import { siteApiContentListingUrl } from "../../lib/urls"
import { WEBSITE_CONTENT_PAGE_SIZE } from "../../constants"

import {
  RelationFilterVariant,
  Website,
  WebsiteContent,
} from "../../types/websites"
import * as websiteHooks from "../../hooks/websites"

jest.mock("../../lib/api/util", () => ({
  ...jest.requireActual("../../lib/api/util"),
  debouncedFetch: jest.fn(),
}))
const debouncedFetch = jest.mocked(apiUtil.debouncedFetch)

jest.mock("../../hooks/websites", () => ({
  ...jest.requireActual("../../hooks/websites"),
  useWebsiteSelectOptions: jest.fn(),
}))
const { formatWebsiteOptions } = websiteHooks
const useWebsiteSelectOptions = jest.mocked(
  websiteHooks.useWebsiteSelectOptions,
)

let capturedSortableSelectProps: any = null
jest.mock("./SortableSelect", () => {
  return {
    __esModule: true,
    default: (props: any) => {
      capturedSortableSelectProps = props
      return (
        <div data-testid="sortable-select">
          {props.value?.map((item: any) => (
            <span key={item.id} data-testid={`sortable-item-${item.id}`}>
              {item.title}
            </span>
          ))}
        </div>
      )
    },
  }
})

let capturedSelectFieldProps: any[] = []
jest.mock("./SelectField", () => {
  return {
    __esModule: true,
    default: (props: any) => {
      capturedSelectFieldProps.push(props)
      return (
        <div data-testid="select-field" data-name={props.name}>
          <input
            data-testid={`select-input-${props.name}`}
            onChange={(e) =>
              props.onChange({
                target: { value: e.target.value, name: props.name },
              })
            }
          />
        </div>
      )
    },
  }
})

describe("RelationField", () => {
  let website: Website,
    helper: IntegrationTestHelper,
    onChange: jest.Mock,
    contentListingItems: WebsiteContent[],
    fakeResponse: any,
    websites: Website[]

  beforeEach(() => {
    website = makeWebsiteDetail()
    helper = new IntegrationTestHelper()
    onChange = jest.fn()
    capturedSelectFieldProps = []
    capturedSortableSelectProps = null

    contentListingItems = R.times(
      () => ({
        ...makeWebsiteContentDetail(),
        metadata: {
          resourcetype: "Image",
        },
      }),
      WEBSITE_CONTENT_PAGE_SIZE,
    )

    fakeResponse = {
      results: contentListingItems,
      count: contentListingItems.length,
      next: null,
      previous: null,
    }

    global.mockFetch.mockResolvedValue({ json: async () => fakeResponse })
    // @ts-expect-error Not fully simulating the response
    debouncedFetch.mockResolvedValue({ json: async () => fakeResponse })

    websites = makeWebsites()
    useWebsiteSelectOptions.mockReturnValue({
      options: formatWebsiteOptions(websites, "name"),
      loadOptions: jest.fn().mockReturnValue({ options: [] }),
    })
  })

  afterEach(() => {
    debouncedFetch.mockClear()
    global.mockFetch.mockClear()
    useWebsiteSelectOptions.mockReset()
  })

  const renderRelationField = (
    props: Partial<React.ComponentProps<typeof RelationField>> = {},
  ) => {
    const defaultProps = {
      collection: "page",
      display_field: "title",
      name: "relation_field",
      multiple: true,
      onChange,
      value: [] as string[],
      contentContext: null,
    }
    return helper.render(
      <WebsiteContext.Provider value={website}>
        <RelationField {...defaultProps} {...props} />
      </WebsiteContext.Provider>,
    )
  }

  const asOption = (item: WebsiteContent) => ({
    value: item.text_id,
    label: item.title,
  })

  //
  ;[true, false].forEach((hasContentContext) => {
    ;[true, false].forEach((withResourcetypeFilter) => {
      ;["other-site", ""].forEach((websiteNameProp) => {
        it(`should render a SelectField with the expected options, ${
          hasContentContext ? "with" : "without"
        } contentContext, ${
          websiteNameProp ? "with" : "without"
        } a website prop, ${
          withResourcetypeFilter ? "with" : "without"
        } a resourcetype filter`, async () => {
          const websiteName = websiteNameProp ? websiteNameProp : website.name
          const contentContext = hasContentContext
            ? [makeWebsiteContentDetail()]
            : null

          const combinedListing = [
            ...(contentContext ?? []),
            ...contentListingItems,
          ]

          renderRelationField({
            value: contentListingItems.map((item) => item.text_id),
            website: websiteNameProp || undefined,
            contentContext,
            filter: withResourcetypeFilter
              ? {
                  filter_type: RelationFilterVariant.Equals,
                  field: "resourcetype",
                  value: "Image",
                }
              : undefined,
          })

          await waitFor(() => {
            const lastProps =
              capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
            expect(lastProps?.options?.length).toBe(combinedListing.length)
          })

          const lastProps =
            capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
          expect(lastProps.options).toEqual(combinedListing.map(asOption))
          expect(lastProps.defaultOptions).toEqual(
            contentListingItems.map(asOption),
          )

          // there should be one or two initial fetches:
          //
          // - a default 10 items to show when a user opens the dropdown
          // - text_ids for the case where contentContext is absent. If it is
          //   included in props, this fetch is skipped
          const defaultUrl = siteApiContentListingUrl
            .param({ name: websiteName })
            .query({
              detailed_list: true,
              content_context: true,
              type: "page",
              offset: 0,
              ...(withResourcetypeFilter ? { resourcetype: "Image" } : {}),
              ...(websiteNameProp ? { published: true } : {}),
            })
            .toString()
          expect(global.fetch).toHaveBeenCalledTimes(1)
          expect(global.fetch).toHaveBeenCalledWith(defaultUrl, {
            credentials: "include",
          })
        })
      })
    })
  })

  describe("cross_site option", () => {
    it("should present default options for websites", async () => {
      renderRelationField({ cross_site: true, value: [] })

      await waitFor(() => {
        expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
      })

      const firstSelectProps = capturedSelectFieldProps[0]
      expect(firstSelectProps.defaultOptions).toEqual(
        formatWebsiteOptions(websites, "name"),
      )
    })

    it.each(["ocw-www", null])(
      "should not filter on published if website is not set",
      async (websiteName) => {
        renderRelationField({
          ...(websiteName ? { website: websiteName } : {}),
          value: [],
        })

        await waitFor(() => {
          expect(global.fetch).toHaveBeenCalled()
        })

        expect(global.fetch).toHaveBeenCalledWith(
          siteApiContentListingUrl
            .query({
              detailed_list: true,
              content_context: true,
              type: "page",
              offset: 0,
              ...(websiteName ? { published: true } : {}),
            })
            .param({ name: websiteName || website.name })
            .toString(),
          { credentials: "include" },
        )
      },
    )

    it("should let the user pick a website and then content within that website", async () => {
      renderRelationField({ cross_site: true, value: [] })

      await waitFor(() => {
        expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
      })

      const firstSelectProps = capturedSelectFieldProps[0]
      await act(async () => {
        firstSelectProps.onChange({
          target: { value: "new-uuid" },
        })
      })

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          siteApiContentListingUrl
            .query({
              detailed_list: true,
              content_context: true,
              type: "page",
              published: true,
              offset: 0,
            })
            .param({
              name: "new-uuid",
            })
            .toString(),
          { credentials: "include" },
        )
      })

      await waitFor(() => {
        expect(capturedSortableSelectProps?.options?.length).toBeGreaterThan(0)
      })

      expect(capturedSortableSelectProps?.options).toEqual(
        contentListingItems.map((item) => ({
          value: item.text_id,
          label: item.title,
        })),
      )

      await act(async () => {
        if (capturedSortableSelectProps?.onChange) {
          capturedSortableSelectProps.onChange([contentListingItems[0].text_id])
        }
      })

      // this expect call is a regression test for the fix for
      // https://github.com/mitodl/ocw-studio/issues/940
      expect(onChange.mock.calls[0][0]).toEqual({
        target: {
          name: "relation_field",
          value: {
            website: website.name,
            content: [
              [contentListingItems[0].text_id, contentListingItems[0].url_path],
            ],
          },
        },
      })
    })
  })

  //
  ;[true, false].forEach((multiple) => {
    it(`should pass the 'multiple===${multiple}' down to the SelectField`, async () => {
      renderRelationField({ multiple })

      await waitFor(() => {
        expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
      })

      const lastProps =
        capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
      expect(lastProps.multiple).toBe(multiple)
    })
  })

  it("should pass a value down to the SelectField", async () => {
    renderRelationField({ value: "foobar" })

    await waitFor(() => {
      expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
    })

    const lastProps =
      capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
    expect(lastProps.value).toBe("foobar")
  })

  it("should filter results", async () => {
    contentListingItems[0].metadata!.testfield = "testvalue"
    renderRelationField({
      filter: {
        field: "testfield",
        filter_type: RelationFilterVariant.Equals,
        value: "testvalue",
      },
    })

    await waitFor(() => {
      expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
    })

    const lastProps =
      capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
    expect(lastProps.options).toEqual([
      {
        label: contentListingItems[0].title,
        value: contentListingItems[0].text_id,
      },
    ])
  })

  //
  ;[
    ["name", "name"],
    ["name.content", "name"],
  ].forEach(([name, expectedName]) => {
    it(`should accept an onChange prop with name=${name}, which gets modified then passed to the child select component`, async () => {
      const onChangeStub = jest.fn()
      renderRelationField({
        onChange: onChangeStub,
        name,
      })

      await waitFor(() => {
        expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
      })

      const lastProps =
        capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
      const numbers = ["one", "two", "three"]
      const fakeEvent = { target: { value: numbers, name } }
      await act(async () => {
        lastProps.onChange(fakeEvent)
      })
      expect(onChangeStub).toHaveBeenCalledWith({
        target: {
          name: expectedName,
          value: {
            website: website.name,
            content: numbers,
          },
        },
      })
    })
  })

  //
  ;[true, false].forEach((withResourcetypeFilter) => {
    it(`should have a loadOptions prop which triggers a debounced fetch of results, ${
      withResourcetypeFilter ? "with" : "without"
    } a resourcetype filter`, async () => {
      let loadOptionsResponse: { options: Option[] }[] = []
      renderRelationField({
        filter: withResourcetypeFilter
          ? {
              filter_type: RelationFilterVariant.Equals,
              field: "resourcetype",
              value: "Image",
            }
          : undefined,
      })

      await waitFor(() => {
        expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
      })

      const lastProps =
        capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
      const loadOptions = lastProps.loadOptions
      const searchString1 = "searchstring1",
        searchString2 = "searchstring2"

      await act(async () => {
        loadOptionsResponse = await Promise.all([
          loadOptions(searchString1, []),
          loadOptions(searchString2, []),
        ])
      })

      const urlForSearch = (search: string) =>
        siteApiContentListingUrl
          .query({
            detailed_list: true,
            content_context: true,
            offset: 0,
            search: search,
            type: "page",
            ...(withResourcetypeFilter ? { resourcetype: "Image" } : {}),
          })
          .param({ name: website.name })
          .toString()
      expect(debouncedFetch).toHaveBeenCalledTimes(2)
      expect(debouncedFetch).toHaveBeenCalledWith(
        "relationfield",
        300,
        urlForSearch(searchString1),
        { credentials: "include" },
      )
      expect(debouncedFetch).toHaveBeenCalledWith(
        "relationfield",
        300,
        urlForSearch(searchString2),
        { credentials: "include" },
      )
      const expectedOptions = loadOptionsResponse.map((res) => res.options)
      expect(expectedOptions).toStrictEqual([
        fakeResponse.results.map(asOption),
        fakeResponse.results.map(asOption),
      ])
    })
  })

  //
  ;[true, false].forEach((valueIsArray) => {
    it(`should omit items listed by valuesToOmit, except those already selected, when value ${
      valueIsArray ? "is" : "is not"
    } an array`, async () => {
      let loadOptionsResponse = { options: [] as Option[] }
      const valuesToOmit = new Set([
        contentListingItems[0].text_id,
        contentListingItems[2].text_id,
        contentListingItems[3].text_id,
      ])
      const value = valueIsArray
        ? [contentListingItems[0].text_id, contentListingItems[1].text_id]
        : contentListingItems[0].text_id
      const expectedResults = fakeResponse.results.filter(
        (_: any, idx: number) => idx !== 2 && idx !== 3,
      )
      const expectedOptions = expectedResults.map(asOption)

      renderRelationField({ valuesToOmit, value })

      await waitFor(() => {
        expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
      })

      const lastProps =
        capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
      const loadOptions = lastProps.loadOptions
      expect(loadOptions).toBeDefined()
      await act(async () => {
        loadOptionsResponse = await loadOptions("", [])
      })

      expect(loadOptionsResponse.options).toStrictEqual(expectedOptions)
    })
  })

  it("should display an error message", async () => {
    global.mockFetch.mockClear()
    const errorResponse = {
      results: undefined,
      count: 0,
      next: null,
      previous: null,
    }
    global.mockFetch.mockResolvedValue({ json: async () => errorResponse })
    renderRelationField()

    await waitFor(() => {
      expect(
        screen.getByText("Unable to fetch entries for this field."),
      ).toBeInTheDocument()
    })
  })

  describe("sortable UI", () => {
    it("should show a sortable UI when the prop is passed", async () => {
      const value = contentListingItems.map((item) => item.text_id)
      renderRelationField({
        multiple: true,
        sortable: true,
        value,
      })

      await screen.findByTestId("sortable-select")

      expect(capturedSortableSelectProps).not.toBeNull()
      expect(capturedSortableSelectProps.value).toStrictEqual(
        value.map((id) => ({
          id,
          title: id,
        })),
      )
    })

    it("should disable already-selected options", async () => {
      const value = contentListingItems.slice(3).map((item) => item.text_id)
      const options = contentListingItems.map((item) => ({
        value: item.text_id,
        label: item.title ?? "title",
      }))
      renderRelationField({
        multiple: true,
        sortable: true,
        value,
      })

      await waitFor(() => {
        expect(capturedSortableSelectProps).not.toBeNull()
      })

      const isOptionDisabled = capturedSortableSelectProps.isOptionDisabled!
      expect(isOptionDisabled).toBeDefined()
      const expected = [false, false, false, ...Array(7).fill(true)]
      expect(options.map(isOptionDisabled)).toEqual(expected)
    })

    it("should be clearable for single select but not multiple", async () => {
      renderRelationField({
        multiple: false,
        value: contentListingItems[0].text_id,
      })

      await waitFor(() => {
        expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
      })

      const singleSelectProps =
        capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
      expect(singleSelectProps.isClearable).toBe(true)

      capturedSelectFieldProps = []

      renderRelationField({
        multiple: true,
        value: [contentListingItems[0].text_id],
      })

      await waitFor(() => {
        expect(capturedSelectFieldProps.length).toBeGreaterThan(0)
      })

      const multiSelectProps =
        capturedSelectFieldProps[capturedSelectFieldProps.length - 1]
      expect(multiSelectProps.isClearable).toBe(false)
    })
  })
})
