// Adapted from this StackOverflow answer: https://stackoverflow.com/a/53229567
type Without<T, U> = { [P in Exclude<keyof T, keyof U>]?: never }
// XOR can be used to define mutually-exclusive types
export type XOR<T, U> = T | U extends Record<string, unknown>
  ? (Without<T, U> & U) | (Without<U, T> & T)
  : T | U
