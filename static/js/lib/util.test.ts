import casual from "casual"
import { ActionPromiseValue } from "redux-query"
import posthog from "posthog-js"
import { checkFeatureFlag } from "./util"

import {
  filenameFromPath,
  isErrorStatusCode,
  isErrorResponse,
  getResponseBodyError,
  isUuid4,
  generateHashCode,
} from "./util"

describe("util", () => {
  it.each([
    { status: 200, isError: false },
    { status: 299, isError: false },
    { status: 300, isError: false },
    { status: 400, isError: true },
    { status: 500, isError: true },
  ])(
    "isErrorResponse returns $isError when status=$status",
    ({ status, isError }) => {
      const response: ActionPromiseValue<any> = {
        status: status,
        body: {},
        duration: casual.integer(),
      }
      expect(isErrorStatusCode(status)).toStrictEqual(isError)
      expect(isErrorResponse(response)).toStrictEqual(isError)
    },
  )

  const errorMsg = "some error"
  it.each([
    {
      responseData: null,
      expectedResult: null,
      desc: "no data",
    },
    {
      responseData: {},
      expectedResult: null,
      desc: "empty data",
    },
    {
      responseData: errorMsg,
      expectedResult: errorMsg,
      desc: "an error string",
    },
    {
      responseData: [errorMsg, "other errors"],
      expectedResult: errorMsg,
      desc: "error strings as a list",
    },
    {
      responseData: { field1: errorMsg },
      expectedResult: { field1: errorMsg },
      desc: "an error object",
    },
    {
      responseData: { errors: errorMsg },
      expectedResult: errorMsg,
      desc: "a namespaced error message as a string",
    },
    {
      responseData: { errors: [errorMsg] },
      expectedResult: errorMsg,
      desc: "a namespaced message as a list",
    },
    {
      responseData: { errors: { field1: errorMsg } },
      expectedResult: { field1: errorMsg },
      desc: "a namespaced error object",
    },
  ])(
    "getResponseBodyError should return the appropriate error data when it receives $desc",
    ({ responseData, expectedResult }) => {
      const resp = responseData
        ? {
            body: responseData,
            status: casual.integer(),
            duration: casual.integer(),
          }
        : null

      const result = getResponseBodyError(resp)
      expect(result).toStrictEqual(expectedResult)
    },
  )

  it(`getResponseBodyError should return null when it receives an empty response`, () => {
    expect(getResponseBodyError(null)).toBeNull()
    // @ts-expect-error Legacy test... Unsure if a responsive without a body is actually possible.
    expect(getResponseBodyError({})).toBeNull()
  })
  ;[
    [
      "http://aws.amazon.com/bucket/32629a023dc541288e430392b51e7b61/32629a023dc541288e430392b51e7b61_filename.jpg",
      "filename.jpg",
    ],
    [
      "http://aws.amazon.com/bucket/32629a02-3dc5-4128-8e43-0392b51e7b61/32629a02-3dc5-4128-8e43-0392b51e7b61_longer_filename.jpg",
      "longer_filename.jpg",
    ],
    ["http://aws.amazon.com/bucket/longer_filename.jpg", "longer_filename.jpg"],
    [
      "/media/text_id/32629a02-3dc5-4128-8e43-0392b51e7b61_filename.jpg",
      "filename.jpg",
    ],
    [
      "/media/text_id/ab3d029952cda060f4afcd811189a591_longer_filename.jpg",
      "longer_filename.jpg",
    ],
    ["/media/text_id/filename.jpg", "filename.jpg"],
  ].forEach(([filepath, expected]) => {
    it("filenameFromPath should return expected values", () => {
      expect(filenameFromPath(filepath)).toBe(expected)
    })
  })

  it("filenameFromPath should return empty string if filepath is null or undefined", () => {
    expect(filenameFromPath(null)).toBe("")
    expect(filenameFromPath(undefined)).toBe("")
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

  describe("checkFeatureFlag", () => {
    afterEach(() => {
      jest.restoreAllMocks()
    })

    it("calls setFlag synchronously with the feature flag status true", () => {
      const setFlagMock = jest.fn()

      jest.spyOn(posthog, "isFeatureEnabled").mockReturnValue(true)

      const result = checkFeatureFlag("test_flag", setFlagMock)

      expect(setFlagMock).toHaveBeenCalledWith(true)
      expect(result).toBeUndefined()
    })

    it("calls setFlag synchronously with the feature flag status false", () => {
      const setFlagMock = jest.fn()

      jest.spyOn(posthog, "isFeatureEnabled").mockReturnValue(false)

      const result = checkFeatureFlag("test_flag", setFlagMock)

      expect(setFlagMock).toHaveBeenCalledWith(false)
      expect(result).toBeUndefined()
    })

    it("calls setFlag before any asynchronous code", async () => {
      expect.assertions(2)
      const setFlagMock = jest.fn()
      jest.spyOn(posthog, "isFeatureEnabled").mockReturnValue(true)

      checkFeatureFlag("test_flag", setFlagMock)

      expect(setFlagMock).toHaveBeenCalledWith(true)

      await Promise.resolve()
      expect(setFlagMock).toHaveBeenCalledTimes(1)
    })
  })
})
