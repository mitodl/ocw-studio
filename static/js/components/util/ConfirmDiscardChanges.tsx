import React, { useCallback } from "react"
import { useLocation } from "react-router"
import Prompt, { MessageFunc } from "./Prompt"
import * as H from "history"

interface Props {
  when: boolean
}

export default function ConfirmDiscardChanges(props: Props) {
  const location = useLocation()
  const message = useCallback<MessageFunc>(
    (nextLocation: H.Location) => {
      const search = new URLSearchParams(nextLocation.search)
      if (search.has("publish")) {
        return "You have unsaved changes. Are you sure you want to publish?"
      } else if (location.pathname !== nextLocation.pathname) {
        return "You have unsaved changes. Are you sure you want to discard your changes?"
      }
      return true
    },
    [location],
  )
  // Cast message to the expected type to resolve type error
  return (
    <Prompt
      when={props.when}
      onBeforeUnload={true}
      message={
        message as unknown as (location: any, action: any) => string | boolean
      }
    />
  )
}
