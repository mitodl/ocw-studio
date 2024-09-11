import { isEmpty, isNil } from "ramda"
import { ActionPromiseValue } from "redux-query"
import { SiteFormValue } from "../types/forms"
import posthog from "posthog-js"

if (SETTINGS.posthog_api_host && SETTINGS.posthog_project_api_key) {
  const environment = SETTINGS.environment
  if (environment === "dev") {
    posthog.debug()
  }
  posthog.init(SETTINGS.posthog_project_api_key, {
    api_host: SETTINGS.posthog_api_host,
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: false,
    cross_subdomain_cookie: false,
    persistence: "localStorage+cookie",
    loaded: function (posthog) {
      posthog.setPersonPropertiesForFlags({
        environment: environment,
      })
    },
  })
  // @ts-expect-error: SETTINGS.user is intentionally untyped
  posthog.identify(SETTINGS.user.email)
}

export const isErrorStatusCode = (statusCode: number): boolean =>
  statusCode >= 400

export const isErrorResponse = (response: ActionPromiseValue<any>): boolean =>
  isErrorStatusCode(response.status)

/*
 * If an HTTP response contains errors in the body, return either a string representing
 */
export const getResponseBodyError = (
  response: ActionPromiseValue<any> | null,
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
  object: Record<string, SiteFormValue>,
): FormData => {
  const formData = new FormData()

  Object.entries(object).forEach(([key, value]) => {
    if (key === "metadata") {
      formData.append(key, JSON.stringify(value))
    } else if (!isNil(value)) {
      formData.append(key, String(value))
    }
  })
  return formData
}

export const filenameFromPath = (filepath: string): string => {
  const basename = filepath.split("/").pop() || ""
  const UUID =
    /^[0-9A-F]{8}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{12}/i
  if (UUID.test(basename)) {
    if (basename.includes("_")) {
      return basename.split("_").slice(1).join("_")
    }
  }
  return basename
}

export const addToMapList = <TKey, TValue>(
  map: Map<TKey, Array<TValue>>,
  key: TKey,
  value: TValue,
): void => {
  const list = map.get(key) ?? []
  map.set(key, [...list, value])
}

const uuid4regex =
  /^[0-9A-F]{8}-[0-9A-F]{4}-[4][0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$/i

export const isUuid4 = (strToTest: string): boolean =>
  uuid4regex.test(strToTest)

export const generateHashCode = (strToHash: string): string => {
  let hash = 0,
    i,
    chr
  if (strToHash.length === 0) {
    return hash.toString()
  }
  for (i = 0; i < strToHash.length; i++) {
    chr = strToHash.charCodeAt(i)
    hash = (hash << 5) - hash + chr
    hash |= 0 // Convert to 32bit integer
  }
  return hash.toString()
}
