import React from "react"
import { render, RenderOptions } from "@testing-library/react"
import { Provider } from "react-redux"
import { Provider as ReduxQueryProvider } from "redux-query-react"
import { createMemoryHistory } from "history"
import { Router, Route } from "react-router"
import {
  NetworkOptions,
  ResponseBody,
  ResponseHeaders,
  ResponseStatus,
  ResponseText
} from "redux-query"
import { when } from "jest-when"
import configureStore from "../store/configureStore"
import { getQueries } from "../lib/redux_query"

import * as networkInterfaceFuncs from "../store/network_interface"

const { makeRequest: mockMakeRequest } = networkInterfaceFuncs as jest.Mocked<
  typeof networkInterfaceFuncs
>
jest.mock("../store/network_interface")

type Reponse = {
  status: ResponseStatus
  body: ResponseBody
  text: ResponseText
  headers: ResponseHeaders
}
type HandleRequest = (
  url: string,
  method: string,
  options?: NetworkOptions
) => Partial<Reponse>

export default class IntegrationTest {
  handleRequest = jest.fn(((url, method, options) => {
    const withOptions = `with options ${JSON.stringify(options)}`
    console.error(
      `Response not specified for ${method} ${url} ${withOptions}.\nDid you forget to mock it?`
    )
    return {}
  }) as HandleRequest)

  constructor() {
    mockMakeRequest.mockClear()
    mockMakeRequest.mockImplementation((url, method, options) => ({
      execute: callback => {
        const response = this.handleRequest(url, method, options)
        const err = null
        const resStatus = response.status ?? 0
        const resBody = response.body ?? undefined
        const resText = response.text ?? undefined
        const resHeaders = response.headers ?? undefined

        callback(err, resStatus, resBody, resText, resHeaders)
      },
      abort: () => {
        throw new Error("Aborts currently unhandled")
      }
    }))
  }

  mockRequest(
    url: string,
    method: "GET" | "POST" | "PATCH" | "DELETE",
    responseBody: unknown,
    code: number,
    options = {}
  ): this {
    when(this.handleRequest)
      .calledWith(url, method, options)
      .mockReturnValue({
        body:   responseBody,
        status: code
      })
    return this
  }
  /**
   * Convenience method for mocking out a GET request
   *
   * pass the API url you want to mock and the object which should be
   * returned as the request body!
   */
  mockGetRequest(url: string, body: unknown, code = 200): this {
    return this.mockRequest(url, "GET", body, code)
  }

  /**
   * Convenience method for mocking out a POST request
   */
  mockPostRequest(url: string, body: unknown, code = 201): this {
    return this.mockRequest(url, "POST", body, code)
  }

  /**
   * Convenience method for mocking out a PATCH request
   */
  mockPatchRequest(url: string, body: unknown, code = 200): this {
    return this.mockRequest(url, "PATCH", body, code)
  }

  /**
   * Convenience method for mocking out a DELETE request
   */
  mockDeleteRequest(url: string, body: unknown, code = 204): this {
    return this.mockRequest(url, "DELETE", body, code)
  }

  render(ui: React.ReactElement, options?: RenderOptions) {
    const store = configureStore({
      entities: {
        websiteDetails: {}
      },
      queries: {}
    })
    const history = createMemoryHistory()
    const renderResult = render(
      <Provider store={store}>
        <ReduxQueryProvider queriesSelector={getQueries}>
          <Router history={history}>
            {/**
             * When location updates, components consuming location via
             * useLocation or useHistory should re-render. But this appears to
             * to not work as expected with memoryHistory. Putting the
             * component inside a route ensures a re-render when location
             * changes.
             *
             * Experimentally, this is not an issue with BrowserRouter
             * which is what we use in the actual app. (Although, almost
             * everything in our App except the Header renders inside a route
             * anyway.)
             *
             * Use React.cloneElement to clone the ui component so that
             * IntegrationHelper.render maintains a similar call signature to
             * @testing-library/react's render method.
             */}
            <Route path="*">{() => React.cloneElement(ui)}</Route>
          </Router>
        </ReduxQueryProvider>
      </Provider>,
      options
    )
    return [renderResult, { history }] as const
  }
}
