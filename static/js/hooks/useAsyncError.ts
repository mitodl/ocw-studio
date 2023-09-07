import { useState, useCallback } from "react"

/**
 * React's Error Boundaries do not catch errors thrown outside its render loop
 * (e.g., async stuff, including event handlers). This hook returns a callback
 * that will re-throw an error inside the render loop.
 *
 * See https://github.com/facebook/react/issues/14981#issuecomment-468460187
 */
const useThrowSynchronously = () => {
  const [_unused, setState] = useState(null)
  return useCallback(
    (e: Error) =>
      setState(() => {
        throw e
      }),
    [],
  )
}

export default useThrowSynchronously
