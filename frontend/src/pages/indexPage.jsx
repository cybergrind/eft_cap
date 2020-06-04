import React, { Component } from "react"
import { connect } from "react-redux"
import { createSelector } from "reselect"
import * as actions from "../actions"
import * as selectors from "../selectors"

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
    const { head, rows } = this.props.table
    // console.log("ROWS: ", rows)
    const head_content = head.map((text, idx) => <th key={`th_${idx}`}>{text}</th>)

    const body = rows.map((row, idx) => {
      const row_content = row.row.map((cell, cell_idx) => {
        const key = `td_${idx}_${cell_idx}`
        let cell_text
        if (["string", "number"].includes(typeof cell)) {
          cell_text = cell
          return <td key={key}>{cell_text}</td>
        } else {
          cell_text = cell.text
          const click_action = () => this.props.dispatch(cell.action)
          return (
            <td key={key} onClick={click_action}>
              {cell_text}
            </td>
          )
        }
      })
      return (
        <tr key={`row_${idx}`} className={row.className}>
          {row_content}
        </tr>
      )
    })

    return (
      <table className="table table-bordered table-sm table-smaller">
        <thead>
          <tr>{head_content}</tr>
        </thead>
        <tbody>{body}</tbody>
      </table>
    )
  }
  render() {
    return (
      <div className="container">
        <div className="row">
          <div className="col col-xl-11">{this.drawTable()}</div>
          <div className="col col-xl-1">{this.drawExits()}</div>
        </div>
      </div>
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
