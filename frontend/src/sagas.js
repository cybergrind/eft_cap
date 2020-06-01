import {
  call,
  put,
  takeLatest,
  delay,
  select,
  takeLeading,
  takeEvery,
  throttle,
} from 'redux-saga/effects'
import { replace, push } from 'connected-react-router'
import ky from 'ky-universal'
import qs from 'query-string'
import * as actions from './actions'
import * as selectors from './selectors'

//
//function getCookie(name) {
//  var cookieValue = null
//  if (document.cookie && document.cookie !== '') {
//    var cookies = document.cookie.split(';')
//    for (var i = 0; i < cookies.length; i++) {
//      var cookie = cookies[i].trim()
//      // Does this cookie string begin with the name we want?
//      if (cookie.substring(0, name.length + 1) === name + '=') {
//        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
//        break
//      }
//    }
//  }
//  return cookieValue
//}
//
//const csrf = getCookie('csrftoken')
//let api = ky.extend({ headers: { 'X-CSRFToken': csrf } })
//
//async function apiUnwrap(image) {
//  const formData = new FormData()
//  formData.append('img_original', image)
//  const data = await api
//    .post('/api/v001/anonymous_unwrap/', { body: formData, timeout: false })
//    .json()
//  console.log('Data is: ', data)
//  return data
//}
//
//function* unwrapImage(action) {
//  const { image } = action.payload
//  try {
//    yield put(actions.unwrapStarted({ image }))
//    const label = yield call(apiUnwrap, image)
//    yield put(actions.unwrapped({ label }))
//  } catch {
//    yield put(actions.unwrapError())
//  }
//}
//
//async function apiStats() {
//  let out = []
//  let page = 1
//  while (true) {
//    const { results, next } = await api
//      .get('/api/v001/api_stats/', { searchParams: { page } })
//      .json()
//    out = [...out, ...results]
//    if (!next) {
//      break
//    }
//    page += 1
//  }
//  return out
//}
//
//function* loadStats(action) {
//  try {
//    yield put(actions.loadingStats())
//    const stats = yield call(apiStats)
//    yield put(actions.statsLoaded({ stats }))
//  } catch (error) {
//    yield put(actions.statsLoadError({ error }))
//  }
//}

function* root() {
//  yield takeLatest(actions.loadStats, loadStats)
}

export default root
