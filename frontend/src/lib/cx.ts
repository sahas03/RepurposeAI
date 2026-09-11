export type ClassValue = string | false | null | undefined

/** Minimal class joiner. No dependency needed for what this app does. */
export function cx(...parts: ClassValue[]): string {
  let out = ''
  for (const p of parts) {
    if (!p) continue
    out = out ? `${out} ${p}` : p
  }
  return out
}
