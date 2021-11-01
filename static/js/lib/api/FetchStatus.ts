/**
 * Represent success or error status for a fetch request
 *
 * This is really simple at present, but if need be could be extended to include
 * status codes, messages, etc in both cases.
 */
export enum FetchStatus {
  Ok,
  Error
}
