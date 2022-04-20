import React, { useEffect } from "react"
import { Prompt as ReactRouterPromp, PromptProps } from "react-router"

interface Props extends PromptProps {
  onBeforeUnload: boolean
  message: string
}

/**
 * A wrapper around ReactRouter's <Prompt /> component which also prompts for
 * confirmation on beforeunload events (if `props.onBeforeUnload` is true).
 */
export default function Prompt(props: Props) {
  const { onBeforeUnload, ...otherProps } = props
  const { when, message } = otherProps
  useEffect(() => {
    if (!onBeforeUnload || !when) return
    const listener = (event: BeforeUnloadEvent) => {
      /**
       * Most browsers won't show this, but Chrome, at least, requires some
       * returnValue to be set.
       */
      event.returnValue = message
      event.preventDefault()
    }
    window.addEventListener("beforeunload", listener, { capture: true })
    const remove = () =>
      window.removeEventListener("beforeunload", listener, { capture: true })
    return remove
  }, [onBeforeUnload, when, message])

  return <ReactRouterPromp {...otherProps} />
}
