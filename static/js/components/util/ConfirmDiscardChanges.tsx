import React from "react"
import Prompt from "./Prompt"

interface Props {
  when: boolean
}

export default function ConfirmDiscardChanges(props: Props) {
  return (
    <Prompt
      when={props.when}
      onBeforeUnload={true}
      message={
        "You have unsaved changes. Are you sure you want to discard your changes?"
      }
    />
  )
}
