import { ActionPromiseValue } from "redux-query"
import { flatten } from "ramda"

import {
  isErrorStatusCode,
  isErrorResponse,
  getResponseBodyError,
  contentFormValuesToPayload,
  contentInitialValues
} from "./util"
import {
  makeWebsiteContentDetail,
  makeWebsiteStarterConfig
} from "../util/factories/websites"

describe("util", () => {
  [
    [200, false],
    [299, false],
    [300, false],
    [400, true],
    [500, true]
  ].forEach(([status, expResult]) => {
    it(`isErrorResponse returns ${String(expResult)} when status=${String(
      status
    )}`, () => {
      const response: ActionPromiseValue<any> = {
        // @ts-ignore
        status: status,
        body:   {}
      }
      // @ts-ignore
      expect(isErrorStatusCode(status)).toStrictEqual(expResult)
      expect(isErrorResponse(response)).toStrictEqual(expResult)
    })
  })

  const errorMsg = "some error"
  ;[
    [null, null, "no data"],
    [{}, null, "empty data"],
    [errorMsg, errorMsg, "an error string"],
    [[errorMsg, "other errors"], errorMsg, "error strings as a list"],
    [{ field1: errorMsg }, { field1: errorMsg }, "an error object"],
    [{ errors: errorMsg }, errorMsg, "a namespaced error message as a string"],
    [{ errors: [errorMsg] }, errorMsg, "a namespaced message as a list"],
    [
      { errors: { field1: errorMsg } },
      { field1: errorMsg },
      "a namespaced error object"
    ]
  ].forEach(([respData, expResult, desc]) => {
    it(`getResponseBodyError should return the appropriate error data when it receives ${desc}`, () => {
      const resp = respData ? { body: respData } : null
      // @ts-ignore
      const result = getResponseBodyError(resp)
      expect(result).toStrictEqual(expResult)
    })
  })

  it(`getResponseBodyError should return null when it receives an empty response`, () => {
    // @ts-ignore
    let result = getResponseBodyError(null)
    expect(result).toBeNull()
    // @ts-ignore
    result = getResponseBodyError({})
    expect(result).toBeNull()
  })

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
