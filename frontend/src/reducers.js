import { combineReducers } from 'redux'
import { connectRouter } from 'connected-react-router'
import * as actions from './actions'
import { handleActions } from 'redux-actions'
import * as CONST from './const'

//const stats = handleActions(
//  {
//    [actions.statsLoaded]: (previous, action) => {
//      const { stats } = action.payload
//      return {
//        ...previous,
//        stats,
//        state: CONST.API.FINISHED,
//      }
//    },
//)

const createRootReducer = history =>
  combineReducers({
    router: connectRouter(history),
    // stats,
  })

export default createRootReducer
