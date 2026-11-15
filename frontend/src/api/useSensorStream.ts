import { useEffect, useRef, useState } from 'react'
import { RingBuf } from '../viz/ringbuf'
import { API_BASE, USE_FIXTURES } from './client'
import type { PositionMsg, SensorSource, Sensors, SimParams, SpectrumMsg } from './types'
import { parseMessage } from './wsMessages'
export const nextBackoff = (attempt: number) => Math.min(500 * 2 ** attempt, 5000)
export interface LinkState { source: SensorSource; connected: boolean; sensors: Sensors; imu_hz: number | null; tof_hz: number | null }
const FIXTURE_LINK: LinkState = { source: 'sim', connected: true, sensors: { movement: true, distance: true }, imu_hz: 100, tof_hz: 40 }

/** Live /ws data. Samples go to refs (drawn on canvas); only link state is React state. */
export function useSensorStream(params: SimParams) {
  const imu = useRef(new RingBuf(1000, 6))
  const tof = useRef(new RingBuf(400, 1))
  const spectrum = useRef<SpectrumMsg | null>(null)
  const position = useRef<PositionMsg | null>(null)
  const currentParams = useRef(params)
  useEffect(() => { currentParams.current = params }, [params])
  const [connected, setConnected] = useState(USE_FIXTURES)
  const [link, setLink] = useState<LinkState | null>(USE_FIXTURES ? FIXTURE_LINK : null)
  useEffect(() => {
    if (USE_FIXTURES) {
      let t = Date.now() / 1000
      const timer = window.setInterval(() => {
        const p = currentParams.current
        for (let i = 0; i < 5; i++) {
          t += 0.01
          imu.current.push(t, [p.tremor_amp * Math.sin(2 * Math.PI * p.tremor_hz * t) + p.noise * Math.sin(t * 123.7), 0, 9.81, 0, 0, 0])
          if (i % 2 === 0) tof.current.push(t, [p.hand_mm])
        }
      }, 50)
      return () => clearInterval(timer)
    }
    let stopped = false
    let attempt = 0
    let retry: number
    let socket: WebSocket | undefined
    function connect() {
      socket = new WebSocket(`${API_BASE.replace(/^http/, 'ws')}/ws`)
      socket.onopen = () => { attempt = 0; setConnected(true) }
      socket.onmessage = event => {
        const m = parseMessage(String(event.data))
        if (!m) return
        switch (m.type) {
          case 'imu': m.samples.forEach((row, i) => imu.current.push(m.t0 + i / m.fs, row)); break
          case 'tof': m.samples_mm.forEach((mm, i) => tof.current.push(m.t0 + m.t[i], [mm])); break
          case 'spectrum': spectrum.current = m; break
          case 'position': position.current = m; break
          case 'status': if (!m.recording) { spectrum.current = null; position.current = null } break
          case 'source': setLink({ source: m.sensor_source, connected: m.connected, sensors: m.sensors, imu_hz: m.imu_hz, tof_hz: m.tof_hz }); break
        }
      }
      socket.onclose = () => {
        if (stopped) return
        setConnected(false)
        retry = window.setTimeout(connect, nextBackoff(attempt++))
      }
      socket.onerror = () => socket?.close()
    }
    connect()
    return () => { stopped = true; clearTimeout(retry); socket?.close() }
  }, [])
  // The board link counts as up only while the backend socket is up and the source reports connected.
  const live = connected && (link?.connected ?? false)
  return { imu, tof, spectrum, position, connected, live, link, source: link?.source ?? null }
}
export type SensorStream = ReturnType<typeof useSensorStream>
