import { createAction } from "redux-actions"

export const wsConnected = createAction("WS_CONNECTED")
export const wsDisconnected = createAction("WS_DISCONNECTED")
export const wsMessage = createAction("WS_MESSAGE")
export const drawTable = createAction("DRAW_TABLE")
