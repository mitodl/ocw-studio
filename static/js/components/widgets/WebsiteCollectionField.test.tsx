import React from "react"
import { waitFor } from "@testing-library/react"

import { IntegrationTestHelper } from "../../testing_utils"
import WebsiteCollectionField, {
  formatOptionsLabelWithShortId,
} from "./WebsiteCollectionField"

import * as websiteHooks from "../../hooks/websites"
import { Website } from "../../types/websites"
import { makeWebsites } from "../../util/factories/websites"

jest.mock("../../hooks/websites", () => ({
  ...jest.requireActual("../../hooks/websites"),
  useWebsiteSelectOptions: jest.fn(),
}))
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
          <button
            data-testid="add-item"
            onClick={() => {
              if (props.options?.[0]) {
                props.onChange([props.options[0].value])
              }
            }}
          >
            Add
          </button>
        </div>
      )
    },
  }
})

describe("WebsiteCollectionField", () => {
  let helper: IntegrationTestHelper,
    onChange: jest.Mock,
    websites: Website[],
    websiteOptions: websiteHooks.WebsiteOption[],
    selectWebsiteOptions: websiteHooks.WebsiteOption[]

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    onChange = jest.fn()
    websites = makeWebsites()
    websiteOptions = websiteHooks.formatWebsiteOptions(websites, "name")
    selectWebsiteOptions = formatOptionsLabelWithShortId(websiteOptions)
    useWebsiteSelectOptions.mockReturnValue({
      options: websiteOptions,
      loadOptions: jest.fn().mockReturnValue({ options: [] }),
    })
    capturedSortableSelectProps = null
  })

  it("should pass published=true to the useWebsiteSelectOptions", async () => {
    helper.render(
      <WebsiteCollectionField
        onChange={onChange}
        name="test-site-collection"
        value={[]}
      />,
    )
    await waitFor(() => {
      expect(useWebsiteSelectOptions).toHaveBeenCalledWith("url_path", true)
    })
  })

  it("should pass things down to SortableSelect", async () => {
    const value = websites.map((website) => ({
      id: website.url_path ?? website.name,
      title: website.title,
    }))

    helper.render(
      <WebsiteCollectionField
        onChange={onChange}
        name="test-site-collection"
        value={value}
      />,
    )
    await waitFor(() => {
      expect(capturedSortableSelectProps).not.toBeNull()
    })
    expect(capturedSortableSelectProps.value).toStrictEqual(value)
    expect(capturedSortableSelectProps.options).toEqual(selectWebsiteOptions)
    expect(capturedSortableSelectProps.defaultOptions).toEqual(
      selectWebsiteOptions,
    )
  })

  it("should let the user add a website, with UUID and title", async () => {
    helper.render(
      <WebsiteCollectionField
        onChange={onChange}
        name="test-site-collection"
        value={[]}
      />,
    )
    await waitFor(() => {
      expect(capturedSortableSelectProps).not.toBeNull()
    })
    capturedSortableSelectProps.onChange([websites[0].name])
    expect(onChange).toHaveBeenCalledWith({
      target: {
        name: "test-site-collection",
        value: [
          {
            id: websites[0].name,
            title: websites[0].title,
          },
        ],
      },
    })
  })

  it("should disable website options that have already been selected", async () => {
    expect(websites.length).toBeGreaterThan(2)
    const value = websites.slice(2).map((website) => ({
      id: website.name,
      title: website.title,
    }))
    helper.render(
      <WebsiteCollectionField
        onChange={onChange}
        name="test-site-collection"
        value={value}
      />,
    )
    await waitFor(() => {
      expect(capturedSortableSelectProps).not.toBeNull()
    })
    const isOptionDisabled = capturedSortableSelectProps.isOptionDisabled!
    expect(isOptionDisabled).toBeDefined()
    const expected = [false, false, ...Array(8).fill(true)]
    expect(websiteOptions.map(isOptionDisabled)).toEqual(expected)
  })
})
