import { ActionPromiseValue } from "redux-query"

import {
  filenameFromPath,
  isErrorStatusCode,
  isErrorResponse,
  getResponseBodyError
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
    ["http://aws.amazon.com/bucket/uuid/uuid_filename.jpg", "filename.jpg"],
    [
      "http://aws.amazon.com/bucket/uuid/uuid_longer_filename.jpg",
      "longer_filename.jpg"
    ],
    ["/media/text_id/uuid_filename.jpg", "filename.jpg"],
    ["/media/text_id/filename.jpg", "filename.jpg"]
  ].forEach(([filepath, expected]) => {
    it("filenameFromPath should return expected values", () => {
      expect(filenameFromPath(filepath)).toBe(expected)
    })
  })
})
