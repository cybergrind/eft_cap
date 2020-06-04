import { combineReducers } from "redux"
import { connectRouter } from "connected-react-router"
import * as actions from "./actions"
import { handleActions } from "redux-actions"
import * as CONST from "./const"

const ws = handleActions(
  {
    [actions.wsConnected]: (previous, action) => {
      return { ...previous, connected: true }
    },
    [actions.wsDisconnected]: (previous, action) => {
      return { ...previous, connected: false }
    },
  },
  { connected: false }
)

const table = handleActions(
  {
    [actions.drawTable]: (previous, action) => {
      const { head = [], rows = [] } = action
      return {
        ...previous,
        head,
        rows,
      }
    },
  },
  { head: [], rows: [] }
)

const exits = handleActions(
  {
    [actions.drawExits]: (previous, action) => {
      return action.exits
    },
  },
  {}
)

const createRootReducer = (history) =>
  combineReducers({
    router: connectRouter(history),
    ws,
    table,
    exits,
  })

export default createRootReducer
