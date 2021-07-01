import { nthArg } from "ramda"

// replace the previous state with the next state without merging
export const nextState = nthArg(1)

export interface PaginatedResponse<Item> {
  count: number | null
  next: string | null
  previous: string | null
  results: Item[]
}
