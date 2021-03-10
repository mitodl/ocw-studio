import { flatten } from "ramda"

import {
  makeWebsiteContentDetail,
  makeWebsiteStarterConfig
} from "../util/factories/websites"
import {
  contentFormValuesToPayload,
  contentInitialValues
} from "./site_content"

describe("site_content", () => {
  describe("contentFormValuesToPayload", () => {
    it("changes the name of markdown", () => {
      const values = {
        content: "some content",
        title:   "a title"
      }
      const fields = makeWebsiteStarterConfig().collections[0].fields
      const payload = contentFormValuesToPayload(values, fields)
      expect(payload).toStrictEqual({
        markdown: "some content",
        title:    "a title"
      })
    })

    it("passes through title and type but not other names", () => {
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
        title:       content.title,
        description: content.metadata?.description,
        content:     content.markdown
      })
    })
  })
})
