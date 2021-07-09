import { act } from "react-dom/test-utils"
import { SinonStub } from "sinon"

import WebsiteCollectionEditor from "./WebsiteCollectionEditor"

import { collectionsApiDetailUrl, collectionsApiUrl } from "../lib/urls"

import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import { createModalState } from "../types/modal_state"
import { makeWebsiteCollection } from "../util/factories/website_collections"
import { WebsiteCollection } from "../types/website_collections"

describe("WebsiteCollectionEditor", () => {
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    hideModalStub: SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    hideModalStub = helper.sandbox.stub()
    render = helper.configureRenderer(WebsiteCollectionEditor, {
      hideModal:  hideModalStub,
      modalState: createModalState("closed", null)
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  describe("adding a new website collection", () => {
    beforeEach(() => {
      helper.handleRequestStub.withArgs(collectionsApiUrl.toString()).returns({
        body:   { id: 32 },
        status: 200
      })
    })

    it("should pass initial values down to the form", async () => {
      const { wrapper } = await render({
        modalState: createModalState("adding", null)
      })
      expect(
        wrapper.find("WebsiteCollectionForm").prop("initialValues")
      ).toEqual({
        title:       "",
        description: ""
      })
    })

    it("should close the modal after saving", async () => {
      const { wrapper } = await render({
        modalState: createModalState("adding", null)
      })
      await act(async () =>
        wrapper.find("WebsiteCollectionForm").prop("onSubmit")!({
          // @ts-ignore
          title: "wow!"
        })
      )
      expect(hideModalStub.called).toBeTruthy()
    })

    it("should allow us to create a new collection", async () => {
      const { wrapper } = await render({
        modalState: createModalState("adding", null)
      })
      await act(async () =>
        wrapper.find("WebsiteCollectionForm").prop("onSubmit")!({
          // @ts-ignore
          title:       "wow!",
          description: "the best one around, by far"
        })
      )

      expect(helper.handleRequestStub.args[0]).toEqual([
        collectionsApiUrl.toString(),
        "POST",
        {
          body: {
            title:       "wow!",
            description: "the best one around, by far"
          },
          credentials: undefined,
          headers:     {
            "X-CSRFTOKEN": ""
          }
        }
      ])
    })
  })

  describe("editing an existing collection", () => {
    let collection: WebsiteCollection

    beforeEach(() => {
      collection = makeWebsiteCollection()

      helper.handleRequestStub
        .withArgs(
          collectionsApiDetailUrl
            .param({
              collectionId: collection.id
            })
            .toString()
        )
        .returns({
          body:   collection,
          status: 200
        })
    })

    it("should pass values from focused website down to form", async () => {
      const { wrapper } = await render({
        modalState: createModalState("editing", collection.id)
      })
      expect(
        wrapper.find("WebsiteCollectionForm").prop("initialValues")
      ).toEqual({
        title:       collection.title,
        description: collection.description
      })
    })

    it("should let us edit an existing collection", async () => {
      const { wrapper } = await render({
        modalState: createModalState("editing", collection.id)
      })
      await act(async () =>
        wrapper.find("WebsiteCollectionForm").prop("onSubmit")!({
          // @ts-ignore
          title:       "new title",
          description: "better description!"
        })
      )
      expect(helper.handleRequestStub.args[1]).toEqual([
        collectionsApiDetailUrl
          .param({
            collectionId: collection.id
          })
          .toString(),
        "PATCH",
        {
          body: {
            ...collection,
            title:       "new title",
            description: "better description!"
          },
          credentials: undefined,
          headers:     {
            "X-CSRFTOKEN": ""
          }
        }
      ])
    })
  })
})
