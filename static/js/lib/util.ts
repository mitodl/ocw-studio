import { isEmpty, isNil } from "ramda"
import { ActionPromiseValue } from "redux-query"
import { SiteFormValue } from "../types/forms"

export const isErrorStatusCode = (statusCode: number): boolean =>
  statusCode >= 400

export const isErrorResponse = (response: ActionPromiseValue<any>): boolean =>
  isErrorStatusCode(response.status)

/*
 * If an HTTP response contains errors in the body, return either a string representing
 */
export const getResponseBodyError = (
  response: ActionPromiseValue<any>
): string | { [key: string]: string } | null => {
  if (!response || !response.body) {
    return null
  }
  // Errors may be namespaced under an "errors" key, or just at the top level of the response body
  const errors = response.body.errors || response.body
  if (isEmpty(errors)) {
    return null
  }
  if (Array.isArray(errors)) {
    // Just return the first error message if a list was returned
    return errors.length === 0 ? null : errors[0]
  }
  return errors
}

export const objectToFormData = (
  object: Record<string, SiteFormValue>
): FormData => {
  const formData = new FormData()

  Object.entries(object).forEach(([key, value]) => {
    if (key === "metadata") {
      formData.append(key, JSON.stringify(value))
    } else if (!isNil(value)) {
      // @ts-ignore
      formData.append(key, value)
    }
  })
  return formData
}

export const filenameFromPath = (filepath: string): string => {
  const basename = filepath.split("/").pop() || ""
  if (basename.includes("_")) {
    return basename
      .split("_")
      .slice(1)
      .join("_")
  }
  return basename
}

export const addToMapList = <TKey, TValue>(
  map: Map<TKey, Array<TValue>>,
  key: TKey,
  value: TValue
): void => {
  const list = map.get(key) ?? []
  map.set(key, [...list, value])
}
