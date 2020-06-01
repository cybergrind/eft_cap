import React from "react"
import { Provider } from "react-redux"
import { Route, Switch } from "react-router"
import { ConnectedRouter } from "connected-react-router"
import { configureStore, history } from "./store"

import "./App.css"
import IndexPage from "./pages/indexPage"

const store = configureStore()

function App() {
  return (
    <Provider store={store}>
      <ConnectedRouter history={history}>
        <>
          <Switch>
            <Route render={() => <IndexPage />} />
          </Switch>
        </>
      </ConnectedRouter>
    </Provider>
  )
}

export default App
