import { act } from "react-dom/test-utils"

import WebsiteCollectionItemForm from "./WebsiteCollectionItemForm"
import { makeWebsiteListing } from "../../util/factories/websites"
import { makeWebsiteCollection } from "../../util/factories/website_collections"
import { Website } from "../../types/websites"
import { siteApiListingUrl, wcItemsApiUrl } from "../../lib/urls"
import { WebsiteCollection } from "../../types/website_collections"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"

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
    const cb = helper.sandbox.stub()

    const websites = makeWebsiteListing()
    const options = websites.map((website: Website) => ({
      label: website.title,
      value: website.uuid
    }))

    // @ts-ignore
    global.fetch = jest.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ results: websites })
      })
    )

    const { wrapper } = await render()
    await act(async () => {
      // @ts-ignore
      await wrapper.find("Field").prop("loadOptions")("searchstring", cb)
    })
    wrapper.update()

    expect(cb.args[0][0]).toEqual(options)
    expect(wrapper.find("SelectField").prop("options")).toEqual(options)
    expect(
      // @ts-ignore
      global.fetch.mock.calls[0]
    ).toEqual([
      siteApiListingUrl
        .query({ offset: 0 })
        .param({ search: "searchstring" })
        .toString()
    ])
  })
})
