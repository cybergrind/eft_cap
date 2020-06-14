import { combineReducers } from "redux"
import { connectRouter } from "connected-react-router"
import * as actions from "./actions"
import { handleActions } from "redux-actions"
import * as CONST from "./const"
import { getClass } from "leaflet/src/dom/DomUtil"

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

function getPlayerClassName(me, player) {
  if (!player) {
    return ""
  }

  const className = []
  const { dist, is_npc, is_scav, is_alive, wanted, group } = player
  if (is_npc) {
    className.push("npc")
  } else {
    className.push("player")
  }
  if (is_scav) {
    className.push("scav")
  }
  if (is_alive) {
    className.push("alive")
  } else {
    className.push("dead")
  }

  if (player.me || (group && group === me.group)) {
    className.push("my_group")
  } else if (group) {
    className.push("other_group")
    className.push(group)
  }

  if (player.me || player.encrypted) {
  } else if (dist < 50) {
    className.push("brawl")
  } else if (dist < 150) {
    className.push("nearby")
  }
  if (is_scav && wanted) {
    className.push("player_wanted")
  }
  return className.join(" ")
}

function getLootClassName(item) {
  const className = ["loot"]
  if (item.wanted) {
    className.push("wanted")
  }
  if (item.dist < 50) {
    className.push("nearby")
  }

  return className.join(" ")
}

function showLoot(loot) {
  let showLoot = loot.filter((x) => x.total_price > 18000)
  showLoot.sort((a, b) => a.dist - b.dist)
  const near = showLoot.slice(0, 3)
  let far = showLoot.slice(3)
  let expensive = far.filter((x) => x.total_price > 70000 || x.wanted)
  let outLoot = [...near, ...expensive]
  for (let item of outLoot) {
    item.className = getLootClassName(item)
  }
  return outLoot
}

const table = handleActions(
  {
    [actions.drawTable]: (previous, action) => {
      const { me = null, players = [], loot = [] } = action
      me.sec_since_update = Math.round(me.sec_since_update / 10)
      let alivePlayers = []
      let deadPlayers = []
      for (let player of players) {
        player.sec_since_update = Math.round(player.sec_since_update / 10)
        player.className = getPlayerClassName(me, player)
        if (player.is_alive) {
          alivePlayers.push(player)
        } else if (player.loot_price > 30_000) {
          deadPlayers.push(player)
        }
      }
      let param = "dist"
      if (me && me.encrypted) {
        param = "sec_since_update"
      }
      alivePlayers.sort((a, b) => a[param] - b[param])
      deadPlayers.sort((a, b) => a[param] - b[param])

      me.className = getPlayerClassName(me, me)

      return {
        ...previous,
        me,
        players: alivePlayers,
        deadPlayers,
        loot: showLoot(loot),
      }
    },
  },
  { me: null, players: [], deadPlayers: [], loot: [] }
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
