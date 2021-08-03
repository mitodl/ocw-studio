import { siteApiContentListingUrl } from "../../lib/urls"
import { Website, WebsiteContentListItem } from "../../types/websites"
import {
  makeWebsiteContentListItem,
  makeWebsiteDetail
} from "../../util/factories/websites"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import ResourceEmbedField from "./ResourceEmbedField"
import { useWebsite } from "../../context/Website"
import { useDebouncedState } from "../../hooks/state"
import { act } from "react-dom/test-utils"
import { useState } from "react"

jest.mock("../../context/Website")
jest.mock("../../hooks/state")

describe("ResourceEmbedField", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    insertEmbedStub: any,
    apiResponse,
    website: Website,
    contentListingItems: WebsiteContentListItem[],
    setStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    insertEmbedStub = helper.sandbox.stub()

    render = helper.configureRenderer(ResourceEmbedField, {
      insertEmbed: insertEmbedStub,
      attach:      "resource"
    })

    website = makeWebsiteDetail()
    // @ts-ignore
    useWebsite.mockReturnValue(website)

    setStub = helper.sandbox.stub()
    // @ts-ignore
    useDebouncedState.mockReturnValue(["", setStub])

    contentListingItems = [
      makeWebsiteContentListItem(),
      makeWebsiteContentListItem()
    ]

    apiResponse = {
      results:  contentListingItems,
      count:    2,
      next:     null,
      previous: null
    }

    helper.handleRequestStub
      .withArgs(
        siteApiContentListingUrl
          .param({
            name: website.name
          })
          .query({ offset: 0, type: "resource" })
          .toString(),
        "GET"
      )
      .returns({
        body:   apiResponse,
        status: 200
      })

    helper.handleRequestStub
      .withArgs(
        siteApiContentListingUrl
          .param({
            name: website.name
          })
          .query({ offset: 0, type: "resource", search: "newFilter" })
          .toString(),
        "GET"
      )
      .returns({
        body:   apiResponse,
        status: 200
      })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should fetch and display resources", async () => {
    const { wrapper } = await render()
    expect(
      wrapper.find(".resource-list .resource").map(el => el.find("h4").text())
    ).toEqual(contentListingItems.map(item => item.title))
  })

  it("should call insertEmbed prop with resources", async () => {
    const { wrapper } = await render()

    wrapper
      .find(".resource-list .resource")
      .at(0)
      .simulate("click")
    expect(
      insertEmbedStub.calledWith(contentListingItems[0].text_id)
    ).toBeTruthy()
  })

  it("should allow the user to filter resources", async () => {
    const setStub = helper.sandbox.stub()
    // @ts-ignore
    useDebouncedState.mockImplementation((initial, _ms) => {
      // this is just to un-debounce to make testing easier
      const [state, setState] = useState(initial)

      return [
        state,
        (update: any) => {
          setStub(update)
          setState(update)
        }
      ]
    })

    const { wrapper } = await render()

    act(() => {
      // @ts-ignore
      wrapper.find(".filter-input").prop("onChange")({
        // @ts-ignore
        currentTarget: { value: "newFilter" }
      })
    })

    expect(setStub.calledWith("newFilter")).toBeTruthy()
    expect(helper.handleRequestStub.args.map(xs => xs[0])).toEqual([
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({ offset: 0, type: "resource" })
        .toString(),
      siteApiContentListingUrl
        .param({
          name: website.name
        })
        .query({ offset: 0, type: "resource", search: "newFilter" })
        .toString()
    ])
  })
})
