import React, { ComponentType } from "react"
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
          const response = this.handleRequestStub(url, method, options)
          const err = null
          const resStatus = (response && response.status) || 0
          const resBody = (response && response.body) || undefined
          const resText = (response && response.text) || undefined
          const resHeaders = (response && response.header) || undefined

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

  configureRenderer(
    Component: ComponentType,
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

      const wrapper = await mount(
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
