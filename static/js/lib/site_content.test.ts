import { flatten } from "ramda"

import {
  makeWebsiteContentDetail,
  makeWebsiteStarterConfig
} from "../util/factories/websites"
import {
  contentFormValuesToPayload,
  contentInitialValues
} from "./site_content"
import { MAIN_PAGE_CONTENT_FIELD } from "../constants"

describe("site_content", () => {
  describe("contentFormValuesToPayload", () => {
    it("changes the name of a 'content' field if it uses the markdown widget", () => {
      const values = {
        title:   "a title",
        content: "some content"
      }
      const fields = [
        {
          label:  "Title",
          name:   "title",
          widget: "string"
        },
        {
          label:  "Content",
          name:   MAIN_PAGE_CONTENT_FIELD,
          widget: "markdown"
        }
      ]
      const payload = contentFormValuesToPayload(values, fields)
      expect(payload).toStrictEqual({
        markdown: "some content",
        title:    "a title"
      })
    })

    it("passes through title and type, and namespaces other fields under 'metadata'", () => {
      const values = {
        title:       "a title",
        type:        "resource",
        description: "a description here"
      }
      const fields = makeWebsiteStarterConfig().collections.find(
        item => item.name === "resource"
      )?.fields
      // @ts-ignore
      const payload = contentFormValuesToPayload(values, fields)
      expect(payload).toStrictEqual({
        title:    "a title",
        type:     "resource",
        metadata: {
          description: "a description here"
        }
      })
    })

    it("converts a payload to a FormData object if a file is included", () => {
      const mockFile = new File([new ArrayBuffer(1)], "file.jpg")
      const values = {
        title:       "a title",
        type:        "resource",
        description: "a description here",
        file:        mockFile
      }
      const fields = makeWebsiteStarterConfig().collections.find(
        item => item.name === "resource"
      )?.fields
      // @ts-ignore
      const payload = contentFormValuesToPayload(values, fields)
      expect(payload instanceof FormData).toBe(true)
    })
  })

  describe("contentInitialValues", () => {
    it("from a content object", () => {
      const content = makeWebsiteContentDetail()
      // combine all possible fields so we can test all code paths
      const fields = flatten(
        makeWebsiteStarterConfig().collections.map(item => item.fields)
      )
      // @ts-ignore
      const payload = contentInitialValues(content, fields)
      expect(payload).toStrictEqual({
        file:                      null,
        title:                     content.title,
        description:               content.metadata?.description,
        [MAIN_PAGE_CONTENT_FIELD]: content.markdown
      })
    })
  })
})
