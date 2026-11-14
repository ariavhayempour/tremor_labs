import { useEffect, useRef, useState } from 'react'
import { RingBuf } from '../viz/ringbuf'
import { API_BASE, getHealth, USE_FIXTURES } from './client'
import type { Health, ImuMsg, SimParams } from './types'
export const nextBackoff = (attempt: number) => Math.min(500 * 2 ** attempt, 5000)
export function useSensorStream(params: SimParams) {
  const imu = useRef(new RingBuf(1000, 6))
  const currentParams = useRef(params)
  useEffect(() => { currentParams.current = params }, [params])
  const [connected, setConnected] = useState(USE_FIXTURES)
  const [source, setSource] = useState<Health['sensor_source'] | null>(USE_FIXTURES ? 'sim' : null)
  useEffect(() => {
    if (USE_FIXTURES) {
      let t = Date.now() / 1000
      const timer = window.setInterval(() => {
        const p = currentParams.current
        for (let i = 0; i < 5; i++) {
          t += 0.01
          imu.current.push(t, [p.amplitude * Math.sin(2 * Math.PI * p.tremor_hz * t) + p.noise * Math.sin(t * 123.7), 0, 9.81, 0, 0, 0])
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
      socket.onopen = () => {
        attempt = 0
        setConnected(true)
        void getHealth().then(h => { if (!stopped) setSource(h.sensor_source) }).catch(() => { if (!stopped) setSource(null) })
      }
      socket.onmessage = event => {
        try {
          const message = JSON.parse(String(event.data)) as ImuMsg
          if (message.type === 'imu' && message.fs > 0 && Array.isArray(message.samples)) {
            message.samples.forEach((row, i) => {
              if (Array.isArray(row) && row.every(Number.isFinite)) imu.current.push(message.t0 + i / message.fs, row)
            })
          }
        } catch { /* Ignore incomplete streaming messages. */ }
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
  return { imu, connected, source }
}
