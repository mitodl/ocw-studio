import { act } from "react-dom/test-utils"

import WebsiteCollectionItemForm from "./WebsiteCollectionItemForm"
import { makeWebsiteListing } from "../../util/factories/websites"
import { makeWebsiteCollection } from "../../util/factories/website_collections"
import { Website } from "../../types/websites"
import { siteApiListingUrl, wcItemsApiUrl } from "../../lib/urls"
import { debouncedFetch } from "../../lib/api/util"
import { WebsiteCollection } from "../../types/website_collections"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"

jest.mock("../../lib/api/util", () => ({
  ...jest.requireActual("../../lib/api/util"),
  debouncedFetch: jest.fn()
}))

describe("WebsiteCollectionItemForm", () => {
  let helper: IntegrationTestHelper,
    websiteCollection: WebsiteCollection,
    render: TestRenderer

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    websiteCollection = makeWebsiteCollection()
    render = helper.configureRenderer(WebsiteCollectionItemForm, {
      websiteCollection
    })

    helper.handleRequestStub
      .withArgs(
        wcItemsApiUrl.param({ collectionId: websiteCollection.id }).toString()
      )
      .returns({ status: 200 })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("should pass initialValues to Formik", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("Formik").prop("initialValues")).toEqual({
      website: undefined
    })
  })

  it("should disable the 'add' button initially", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("button").prop("disabled")).toBeTruthy()
  })

  it("onSubmit should issue request then resetForm", async () => {
    const resetFormStub = helper.sandbox.stub()

    const { wrapper } = await render()
    act(() => {
      wrapper
        .find("Formik")
        // @ts-ignore
        .prop("onSubmit")!({ website: "hey!" }, { resetForm: resetFormStub })
    })
    expect(helper.handleRequestStub.args[0]).toEqual([
      wcItemsApiUrl.param({ collectionId: websiteCollection.id }).toString(),
      "POST",
      {
        body:    { website: "hey!" },
        headers: {
          "X-CSRFTOKEN": ""
        },
        credentials: undefined
      }
    ])
    expect(resetFormStub.called).toBeTruthy()
  })

  it("should pass placeholder to SelectField", async () => {
    const { wrapper } = await render()
    expect(wrapper.find("Field").prop("placeholder")).toBe(
      "Find a course to add to this collection"
    )
  })

  it("should pass loadOptions function down to SelectField", async () => {
    const cb = jest.fn()

    const asOption = (website: Website) => ({
      label: website.title,
      value: website.uuid
    })
    // add one duplicate value to at the end of websites2 to verify it gets removed
    const websites1 = makeWebsiteListing(),
      websites2 = [...makeWebsiteListing(), websites1[0]]
    const options1 = websites1.map(asOption),
      options2 = websites2.map(asOption)
    const expectedCombinedOptions = [
      ...options1,
      ...options2.slice(0, options2.length - 1)
    ]

    // null for a fetch which was not made because there was another later one scheduled
    // @ts-ignore
    debouncedFetch.mockResolvedValueOnce(null)
    // @ts-ignore
    debouncedFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ results: websites1 })
    })
    // @ts-ignore
    debouncedFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ results: websites2 })
    })

    const { wrapper } = await render()
    await act(async () => {
      // @ts-ignore
      await wrapper.find("Field").prop("loadOptions")("sear", cb)
      // @ts-ignore
      await wrapper.find("Field").prop("loadOptions")("searchstring1", cb)
      // @ts-ignore
      await wrapper.find("Field").prop("loadOptions")("searchstring2", cb)
    })
    wrapper.update()

    expect(cb).toBeCalledTimes(2)
    expect(cb).toHaveBeenNthCalledWith(1, options1)
    expect(cb).toHaveBeenNthCalledWith(2, options2)
    expect(wrapper.find("SelectField").prop("options")).toEqual(
      expectedCombinedOptions
    )
    for (const search of ["searchstring1", "searchstring2"]) {
      expect(debouncedFetch).toBeCalledWith(
        "website-collection",
        300,
        siteApiListingUrl
          .query({ offset: 0 })
          .param({ search: search })
          .toString(),
        { credentials: "include" }
      )
    }
  })
})
