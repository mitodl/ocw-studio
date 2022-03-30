/**
 * Create a new type that is the same as T except with properties K required and
 * not null/undefined.
 */
type NonNullableProps<T, K extends keyof T> = T &
  {
    [L in K]-?: NonNullable<Required<T>[L]>
  }

/**
 * Return a predicate `obj => boolean` that asserts `obj[key]` is not null and
 * is not undefined.
 */
export const hasNotutilNilProp = <T, K extends keyof T>(key: K) => (
  obj: T
): obj is NonNullableProps<T, K> => {
  return obj[key] !== undefined && obj[key] !== null
}

/**
 * Type predicate that asserts value is not null or undefined.
 */
export const isNotNil = <T>(value: T): value is NonNullable<T> => {
  return value !== undefined && value !== null
}
