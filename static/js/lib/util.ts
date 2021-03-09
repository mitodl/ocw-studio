import { isEmpty } from "ramda"
import { ActionPromiseValue } from "redux-query"

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
