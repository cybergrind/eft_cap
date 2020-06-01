import React, { Component } from "react"
import { connect } from "react-redux"
import { createSelector } from "reselect"
import * as actions from "../actions"
import * as selectors from "../selectors"

class IndexPage extends Component {
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
    return <div className="container">{this.drawTable()}</div>
  }
}
const indexSelector = createSelector(selectors.ws, selectors.table, (ws, table) => {
  return { ws, table }
})
export default connect(indexSelector)(IndexPage)
