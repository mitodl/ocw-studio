import { ActionPromiseValue } from "redux-query"

import {
  filenameFromPath,
  isErrorStatusCode,
  isErrorResponse,
  getResponseBodyError,
  isUuid4,
  generateHashCode,
  isExternalLinkId
} from "./util"

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
  ;[
    [
      "http://aws.amazon.com/bucket/32629a023dc541288e430392b51e7b61/32629a023dc541288e430392b51e7b61_filename.jpg",
      "filename.jpg"
    ],
    [
      "http://aws.amazon.com/bucket/32629a02-3dc5-4128-8e43-0392b51e7b61/32629a02-3dc5-4128-8e43-0392b51e7b61_longer_filename.jpg",
      "longer_filename.jpg"
    ],
    ["http://aws.amazon.com/bucket/longer_filename.jpg", "longer_filename.jpg"],
    [
      "/media/text_id/32629a02-3dc5-4128-8e43-0392b51e7b61_filename.jpg",
      "filename.jpg"
    ],
    [
      "/media/text_id/ab3d029952cda060f4afcd811189a591_longer_filename.jpg",
      "longer_filename.jpg"
    ],
    ["/media/text_id/filename.jpg", "filename.jpg"]
  ].forEach(([filepath, expected]) => {
    it("filenameFromPath should return expected values", () => {
      expect(filenameFromPath(filepath)).toBe(expected)
    })
  })

  it("isUuid4 should return true if the value is a valid UUID v4", () => {
    const uuid4 = "32629a02-3dc5-4128-8e43-0392b51e7b61"
    const notUuid4 = "abc"
    expect(isUuid4(uuid4)).toBe(true)
    expect(isUuid4(notUuid4)).toBe(false)
  })

  it("generateHashCode should produce a numeric hash code for some string value", () => {
    expect(generateHashCode("abcdefg")).toEqual("-1206291356")
    expect(generateHashCode("http://example.com")).toEqual("-631280213")
  })

  it("isExternalLinkId returns true if the string starts with the external link prefix", () => {
    expect(isExternalLinkId("external-1234")).toBe(true)
    expect(isExternalLinkId("not-external-link")).toBe(false)
  })
})
