import React, { Component } from "react"
import L, { divIcon } from "leaflet"
import { Map, Marker, ImageOverlay, Popup, CircleMarker } from "react-leaflet"
import DivIcon from "react-leaflet-div-icon"
import deadIcon from "../icons/dead.svg"

function Player({ className } = {}) {
  return `<svg
      class="pointer ${className}"
      viewBox="-1 -1 2 2"
      version="1.1"
      xmlns="http://www.w3.org/2000/svg"
    >
<g>
      <circle cx="0" cy="0" r="1" />
</g>
</svg>`
}

class MyMap extends Component {
  // <img src={process.env.PUBLIC_URL + "/maps/shoreline.png"} />
  constructor() {
    super()
    this.state = { zoom: 0, position: [0, 0] }
  }
  dragEnd = (e) => {
    console.log(e.target._latlng)
  }
  changeZoom = (e) => {
    this.setState({ zoom: e.target._zoom })
  }

  drawMarkers() {
    const { markers = [] } = this.props
    return markers.map((marker) => {
      if (!marker) {
        return null
      }
      const pos = marker.pos
      let key = marker.name

      if (!pos.x) {
        return null
      }

      return (
        <Marker
          position={[pos.z, pos.x]}
          key={key}
          icon={L.divIcon({
            html: Player(marker),
            iconSize: [10, 10],
          })}
        ></Marker>
      )
    })
  }

  render() {
    const { position = [-332.4, -148.9] } = this.props

    const picSize = [
      [0, 0],
      [1500, 2415],
    ]
    // const position = [-332.4, -148.9]

    const bounds__ = [
      [-439.9, -1209.3],
      [707, 632],
    ]
    const bounds = [
      [-443.5, -1211],
      [703.3, 633.8],
    ]

    const mapBounds = [
      [-447.89, -1041],
      [589.89, 519],
    ]
    const icon = L.icon({
      iconUrl: "https://unpkg.com/leaflet@1.6.0/dist/images/marker-icon.png",
    })
    const marker = (
      <Marker position={position} draggable={true} onDragend={this.dragEnd}>
        <Popup>HELP ME</Popup>
      </Marker>
    )
    return (
      <div id="mapContainer">
        <Map
          center={this.state.position}
          crs={L.CRS.Simple}
          id="myMap"
          maxBounds={mapBounds}
          minZoom={-3}
          zoom={this.state.zoom}
          onZoomend={this.changeZoom}
        >
          <ImageOverlay
            url={process.env.PUBLIC_URL + "/maps/shoreline.png"}
            bounds={bounds}
            opacity={1}
          ></ImageOverlay>
          {marker}
          {this.drawMarkers()}
        </Map>
      </div>
    )
  }
}

export default MyMap
