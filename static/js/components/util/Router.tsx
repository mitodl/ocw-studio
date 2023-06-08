import React, { useState } from "react"
import { BrowserRouter, BrowserRouterProps } from "react-router-dom"
import PromptConfirmationModal, {
  GetUserConfirmation
} from "./PromptConfirmationModal"

/**
 * Wrapper around BrowserRouter that uses a custom getUserConfirmation modal
 * instead of the default window.confirm.
 */
const CustomConfirmBrowserRouter: React.FC<
  Omit<BrowserRouterProps, "getUserConfirmation">
> = props => {
  const [getUserConfirmation, setGetUserConfirmation] =
    useState<GetUserConfirmation | null>(null)
  return (
    <>
      {getUserConfirmation && (
        <BrowserRouter getUserConfirmation={getUserConfirmation}>
          {props.children}
        </BrowserRouter>
      )}
      <PromptConfirmationModal
        ref={ref => {
          if (ref === null) return
          setGetUserConfirmation(() => ref)
        }}
      />
    </>
  )
}

export default CustomConfirmBrowserRouter
