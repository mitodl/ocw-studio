import React, { useCallback } from "react"
import { useLocation } from 'react-router'
import { Location, Action } from 'history'
import Prompt from "./Prompt"

interface Props {
  when: boolean
}

type MessageFunc = (location: Location, action: Action) => boolean | string

export default function ConfirmDiscardChanges(props: Props) {
  const location = useLocation()
  const message = useCallback<MessageFunc>(nextLocation => {
    const search = new URLSearchParams(nextLocation.search)
    if (search.has('publish')) {
      return 'You have unsaved changes. Are you sure you want to publish?'
    } else if (location.pathname !== nextLocation.pathname) {
      return "You have unsaved changes. Are you sure you want to discard your changes?"
    }
    return true
  }, [location])
  return (
    <Prompt
      when={props.when}
      onBeforeUnload={true}
      message={message}
    />
  )
}
