"use client"

import { useEffect, useRef } from "react"
import type { Map as LeafletMap } from "leaflet"

import "leaflet/dist/leaflet.css"

export type IncidentStatistic = {
  place: string
  type: string
  total_count: number
  updated_at: string
}

export type KnownPlace = {
  name: string
  latitude: number
  longitude: number
}

type IncidentHotspotMapProps = {
  statistics: IncidentStatistic[]
  known_places: KnownPlace[]
}

const INCIDENT_TYPES = [
  { name: "Rights Violations", color: "#DC2626", emoji: "🔴" },
  { name: "Casualties", color: "#F97316", emoji: "🟠" },
  { name: "Displacements", color: "#2563EB", emoji: "🔵" },
  { name: "Severe Hunger", color: "#EAB308", emoji: "🟡" },
] as const

function place_key(value: string): string {
  return value.trim().toLocaleLowerCase()
}

function category_dot_radius(reports: number): number {
  // Keep category markers compact so nearby hotspots remain easy to distinguish.
  return Math.min(12, Math.max(6, 5 + Math.sqrt(reports)))
}

function escape_html(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[character] ?? character)
}

/** Shows one category-coloured dot for each reported incident type at a known place. */
export function IncidentHotspotMap({ statistics, known_places }: IncidentHotspotMapProps) {
  const map_element = useRef<HTMLDivElement>(null)
  const map_instance = useRef<LeafletMap | null>(null)

  useEffect(() => {
    let cancelled = false

    async function render_map() {
      const leaflet = await import("leaflet")
      if (cancelled || !map_element.current) return

      map_instance.current?.remove()
      const map = leaflet.map(map_element.current, { scrollWheelZoom: false })
      map_instance.current = map

      leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map)

      const totals = new Map<string, { place: string; counts: Record<string, number>; total: number; updated_at: string }>()
      for (const row of statistics) {
        if (!INCIDENT_TYPES.some((incident_type) => incident_type.name === row.type)) continue
        const key = place_key(row.place)
        const entry = totals.get(key) ?? { place: row.place.trim(), counts: {}, total: 0, updated_at: row.updated_at }
        entry.counts[row.type] = (entry.counts[row.type] ?? 0) + Math.max(0, Number(row.total_count) || 0)
        entry.total += Math.max(0, Number(row.total_count) || 0)
        if (new Date(row.updated_at).getTime() > new Date(entry.updated_at).getTime()) entry.updated_at = row.updated_at
        totals.set(key, entry)
      }

      const rendered_place_keys = new Set<string>()
      const place_marker_groups = known_places.flatMap((known_place) => {
        const known_place_key = place_key(known_place.name)
        if (rendered_place_keys.has(known_place_key)) return []
        rendered_place_keys.add(known_place_key)
        const entry = totals.get(known_place_key)
        if (!entry || entry.total < 1) return []

        const reported_types = INCIDENT_TYPES.filter((incident_type) => (entry.counts[incident_type.name] ?? 0) > 0)
        const connector = reported_types.length > 1
          ? leaflet.polyline([], { color: "#1E3A8A", dashArray: "3 4", interactive: false, opacity: 0.65, weight: 2 }).addTo(map)
          : null
        const category_markers = reported_types.map((incident_type) => {
          const marker = leaflet.circleMarker([known_place.latitude, known_place.longitude], {
            radius: category_dot_radius(entry.counts[incident_type.name]),
            color: incident_type.color,
            fillColor: incident_type.color,
            fillOpacity: 0.8,
            weight: 1.5,
          }).addTo(map)
          const hotspot_details = `<div class="incident-hotspot-popup"><h3>📍 ${escape_html(known_place.name)}</h3><p class="incident-hotspot-total">${incident_type.emoji} ${incident_type.name}</p><p>Count: <strong>${entry.counts[incident_type.name]}</strong></p></div>`

          marker.bindPopup(hotspot_details)
          marker.bindTooltip(hotspot_details, {
            className: "incident-hotspot-tooltip",
            direction: "auto",
            offset: [0, -8],
            opacity: 1,
            sticky: true,
          })
          return {
            marker,
            origin: leaflet.latLng(known_place.latitude, known_place.longitude),
            offset: [0, 0] as [number, number],
          }
        })

        return [{ category_markers, connector }]
      })
      const markers = place_marker_groups.flatMap(({ category_markers }) => category_markers)

      // Lay every marker at a shared coordinate out around its origin. This also
      // covers differently named known places that happen to use the same point.
      const markers_by_coordinate = new Map<string, typeof markers>()
      markers.forEach((marker_details) => {
        const coordinate_key = `${marker_details.origin.lat.toFixed(6)},${marker_details.origin.lng.toFixed(6)}`
        const coordinate_markers = markers_by_coordinate.get(coordinate_key) ?? []
        coordinate_markers.push(marker_details)
        markers_by_coordinate.set(coordinate_key, coordinate_markers)
      })
      markers_by_coordinate.forEach((coordinate_markers) => {
        if (coordinate_markers.length === 1) return

        const largest_radius = Math.max(...coordinate_markers.map(({ marker }) => marker.getRadius()))
        const separation = largest_radius / Math.sin(Math.PI / coordinate_markers.length) + 3
        coordinate_markers.forEach((marker_details, index) => {
          const angle = (2 * Math.PI * index) / coordinate_markers.length - Math.PI / 2
          marker_details.offset = [Math.cos(angle) * separation, Math.sin(angle) * separation]
        })
      })

      const position_category_markers = () => {
        place_marker_groups.forEach(({ category_markers, connector }) => {
          const dot_locations = category_markers.map(({ marker, origin, offset }) => {
            const origin_point = map.latLngToLayerPoint(origin)
            const dot_location = map.layerPointToLatLng(origin_point.add(offset))
            marker.setLatLng(dot_location)
            return dot_location
          })
          if (connector) connector.setLatLngs(dot_locations)
        })
      }

      if (markers.length > 0) {
        map.fitBounds(leaflet.featureGroup(markers.map(({ marker }) => marker)).getBounds().pad(0.2), { maxZoom: 8 })
      } else {
        map.setView([5, 25], 3)
      }
      position_category_markers()
      map.on("zoomend moveend", position_category_markers)
      window.setTimeout(() => map.invalidateSize(), 0)
    }

    void render_map()
    return () => {
      cancelled = true
      map_instance.current?.remove()
      map_instance.current = null
    }
  }, [known_places, statistics])

  return <div ref={map_element} className="h-[360px] w-full sm:h-[460px]" aria-label="Incident hotspot map" role="img" />
}
