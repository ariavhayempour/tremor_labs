export class RingBuf {
  private rows: { t: number; values: number[] }[]
  private cursor = 0
  size = 0
  readonly capacity: number
  readonly width: number
  constructor(capacity: number, width: number) { this.capacity = capacity; this.width = width; this.rows = new Array(capacity) }
  push(t: number, values: number[]) {
    this.rows[this.cursor] = { t, values: values.slice(0, this.width) }
    this.cursor = (this.cursor + 1) % this.capacity
    this.size = Math.min(this.size + 1, this.capacity)
  }
  forEach(fn: (t: number, values: number[]) => void) {
    for (let i = 0; i < this.size; i++) {
      const row = this.rows[(this.cursor - this.size + i + this.capacity) % this.capacity]
      fn(row.t, row.values)
    }
  }
  last() { return this.size ? this.rows[(this.cursor - 1 + this.capacity) % this.capacity] : undefined }
  clear() { this.cursor = 0; this.size = 0 }
}
