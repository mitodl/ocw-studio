import React, { ComponentType, FunctionComponent } from "react"
import { mount, ReactWrapper } from "enzyme"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { createMemoryHistory, MemoryHistory, Update, State } from "history"
import { Provider } from "react-redux"
import { Provider as ReduxQueryProvider } from "redux-query-react"
import { Router } from "react-router"
import { Action } from "redux"

import { ReduxState } from "../reducers"
import configureStore, { Store } from "../store/configureStore"
import { getQueries } from "../lib/redux_query"

import * as networkInterfaceFuncs from "../store/network_interface"

export default class IntegrationTestHelper {
  browserHistory: MemoryHistory
  sandbox: SinonSandbox
  actions: Array<Action>
  handleRequestStub: SinonStub
  currentLocation: Update<State> | null
  scrollIntoViewStub: SinonStub
  wrapper?: ReactWrapper | null
  // just roll with it :)
  realWarn: any

  constructor() {
    this.sandbox = sinon.createSandbox({})
    this.actions = []

    this.scrollIntoViewStub = this.sandbox.stub()
    window.HTMLDivElement.prototype.scrollIntoView = this.scrollIntoViewStub
    window.HTMLFieldSetElement.prototype.scrollIntoView = this.scrollIntoViewStub
    this.browserHistory = createMemoryHistory()
    this.currentLocation = null
    this.wrapper = null
    this.browserHistory.listen(url => {
      this.currentLocation = url
    })

    const defaultResponse = {
      body:   {},
      status: 200
    }
    this.handleRequestStub = this.sandbox.stub().returns(defaultResponse)
    this.sandbox
      .stub(networkInterfaceFuncs, "makeRequest")
      .callsFake((url, method, options) => ({
        execute: callback => {
          const response = this.handleRequestStub(url, method, options) ?? {}
          const err = null
          const resStatus = response.status ?? 0
          const resBody = response.body ?? undefined
          const resText = response.text ?? undefined
          const resHeaders = response.header ?? undefined

          callback(err, resStatus, resBody, resText, resHeaders)
        },
        abort: () => {
          throw new Error("Aborts currently unhandled")
        }
      }))
    this.realWarn = console.warn
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    console.warn = () => {}
  }

  /**
   * Convenience method for mocking out a GET request
   *
   * pass the API url you want to mock and the object which should be
   * returned as the request body!
   */
  mockGetRequest(url: string, body: unknown): void {
    this.handleRequestStub.withArgs(url, "GET").returns({
      body,
      status: 200
    })
  }

  cleanup(unmount = true): void {
    this.actions = []
    this.sandbox.restore()

    if (this.wrapper && unmount) {
      this.wrapper.unmount()
      delete this.wrapper
      this.wrapper = null
    }
    console.warn = this.realWarn
  }

  /**
   * Configure the integration test renderer!
   *
   * Takes a component, some defaultProps, and a defaultState for
   * the Redux store and returns a render function which can be used
   * to render the component and then make assertions and so on about it.
   *
   * Usage example:
   *
   * ```ts
   * const render = helper.configureRenderer(
   *   MyComponent, { prop: 'default value' }
   * )
   * const { wrapper, store } = await render()
   * ```
   */
  configureRenderer(
    Component: ComponentType<any> | FunctionComponent<any>,
    defaultProps = {},
    defaultState?: ReduxState
  ) {
    return async (
      extraProps = {},
      beforeRenderActions = [],
      perRenderDefaultState?: ReduxState
    ): Promise<{
      wrapper: ReactWrapper
      store: Store
    }> => {
      const store = configureStore(defaultState ?? perRenderDefaultState)
      beforeRenderActions.forEach(action => store.dispatch(action))

      const wrapper = mount(
        <Provider store={store}>
          <ReduxQueryProvider queriesSelector={getQueries}>
            <Router history={this.browserHistory}>
              <Component {...defaultProps} {...extraProps} />
            </Router>
          </ReduxQueryProvider>
        </Provider>
      )
      this.wrapper = wrapper
      wrapper.update()
      return { wrapper, store }
    }
  }
}

export type TestRenderer = ReturnType<
  IntegrationTestHelper["configureRenderer"]
>
