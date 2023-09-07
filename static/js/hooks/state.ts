import { useState, useCallback, ChangeEvent } from "react"
import { debounce, DebouncedFunc } from "lodash"

/**
 * A debounced state! It works just like `useState`, but `setState`
 * calls are debounced by `delay` ms. Usage example:
 *
 * ```ts
 * const [state, setStateDebounced] = useDebouncedState(
 *   "My Initial Value",   // initial value
 *   300                   // how long to delay updating state
 * )
 * ```
 *
 * This uses `_.debounce` under the hood, so updates can be made
 * immediately by calling the `.flush()` method on `setStateDebounced`
 * if needed.
 */
export function useDebouncedState<T>(
  initialState: T,
  delay: number,
): [T, DebouncedFunc<(n: T) => void>] {
  const [state, setState] = useState<T>(initialState)

  // eslint can't infer the requirements of this function because
  // it's wrapped in `debounce`, but we can manually verify that
  // it is dependent on just `setState` and `delay`.
  //
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const setStateDebounced = useCallback(
    debounce((nextval: T) => setState(nextval), delay),
    [setState, delay],
  )

  return [state, setStateDebounced]
}

type TextInputRetProps = [string, (e: ChangeEvent<HTMLInputElement>) => void]

/**
 * A little utility hook for the boilerplate you need to hold the state
 * for a single text input.
 */
export function useTextInputState(
  initialValue: string | (() => string) = "",
): TextInputRetProps {
  const [inputState, setInputState] = useState<string>(initialValue)

  const setSearchInputCB = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      e.preventDefault()
      setInputState(e.target.value)
    },
    [setInputState],
  )

  return [inputState, setSearchInputCB]
}
