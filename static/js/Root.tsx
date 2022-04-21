import React from "react"
import { Provider } from "react-redux"
import { Provider as ReduxQueryProvider } from "redux-query-react"
import { Store } from "./store/configureStore"
import Router from './components/util/Router'

import App from "./pages/App"
import { getQueries } from "./lib/redux_query"

export interface RootProps {
  store: Store
}
export default function Root(props: RootProps): JSX.Element {
  const { store } = props
  return (
    <div>
      <Provider store={store}>
        <ReduxQueryProvider queriesSelector={getQueries}>
          <Router>
            <App />
          </Router>
        </ReduxQueryProvider>
      </Provider>
    </div>
  )
}
