import React, { Component } from "react"
import { connect } from "react-redux"
import { createSelector } from "reselect"
import * as actions from "../actions"
import * as selectors from "../selectors"
import Map from "../components/map"

class IndexPage extends Component {
  drawExits() {
    const rows = []
    for (const [key, value] of Object.entries(this.props.exits)) {
      rows.push(
        <tr key={key} className={`exit_${value}`}>
          <td>{key}</td>
          <td>{value}</td>
        </tr>
      )
    }

    return (
      <table className="exits table table-smaller">
        <thead>
          <tr>
            <td>Name</td>
            <td>Status</td>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    )
  }

  drawTable() {
    const HEAD = ["Dist", "VDist", "Angle", "Name", "Coord", "Is Alive"]
    const { me, players, deadPlayers, loot } = this.props.table
    const head_content = HEAD.map((text, idx) => <th key={`th_${idx}`}>{text}</th>)

    const playerRows = [me, ...players, ...deadPlayers].map((player, idx) => {
      if (!player) {
        return <></>
      }
      const { name, angle, is_alive, dist, vdist, className, pos } = player
      if (player.encrypted) {
        return (
          <tr key={name} className={className}>
            <td></td>
            <td></td>
            <td></td>
            <td>{name}</td>
            <td>Updated: {player.sec_since_update * 10} sec ago</td>
            <td></td>
          </tr>
        )
      }

      return (
        <tr key={name} className={className}>
          <td>{dist}</td>
          <td>{vdist}</td>
          <td>{angle}</td>
          <td>{name}</td>
          <td>{JSON.stringify(pos)}</td>
          <td>{is_alive}</td>
        </tr>
      )
    })
    const lootRows = loot.map((item) => {
      const { id, name, angle, vdist, dist, total_price, className, action } = item
      const clickAction = () => this.props.dispatch(action)
      return (
        <tr key={id} className={className}>
          <td>{dist}</td>
          <td>{vdist}</td>
          <td>{angle}</td>
          <td>{name}</td>
          <td>Price: {total_price}</td>
          <td onClick={clickAction}>Hide</td>
        </tr>
      )
    })
    return (
      <table className="table table-bordered table-sm table-smaller">
        <thead>
          <tr>{head_content}</tr>
        </thead>
        <tbody>
          {playerRows}
          {lootRows}
        </tbody>
      </table>
    )
  }

  render() {
    const { me, players, deadPlayers } = this.props.table
    let position = [0, 0]
    if (me) {
      const c = me.pos
      position = [c.z, c.x]
    }
    return (
      <>
        <div className="container">
          <div className="row">
            <div className="col col-xl-11">{this.drawTable()}</div>
            <div className="col col-xl-1">{this.drawExits()}</div>
          </div>
        </div>
        {/*<Map position={position} markers={[me, ...players, ...deadPlayers]} />*/}
      </>
    )
  }
}
const indexSelector = createSelector(
  selectors.ws,
  selectors.table,
  selectors.exits,
  (ws, table, exits) => {
    return { ws, table, exits }
  }
)
export default connect(indexSelector)(IndexPage)
