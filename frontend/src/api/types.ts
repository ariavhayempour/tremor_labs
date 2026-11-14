export interface Health { sensor_source: 'sim' | 'board' | 'replay' }
export interface SimParams { tremor_hz: number; amplitude: number; noise: number; hand_height: number }
export interface ImuMsg { type: 'imu'; t0: number; fs: number; samples: number[][] }
export const defaultSim: SimParams = { tremor_hz: 5, amplitude: 0.3, noise: 0.02, hand_height: 220 }
