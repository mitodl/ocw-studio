import React, { useCallback, useEffect, useState } from "react"
import { useAppSelector } from "../hooks/redux"
import Dialog from "./Dialog"

const AuthenticationAlert: React.FC = () => {
  const { authenticationErrors } = useAppSelector((state) => state.user)
  const [isDismissed, setIsDismissed] = useState(false)
  useEffect(() => setIsDismissed(false), [authenticationErrors])
  const dismiss = useCallback(() => setIsDismissed(true), [])
  const goToLogin = useCallback(() => {
    window.location.href = "/login/saml/?idp=default"
  }, [])

  const isVisible = authenticationErrors > 0 && !isDismissed
  if (!isVisible) return null
  return (
    <Dialog
      headerContent={"Session Expired"}
      bodyContent="Your session has expired. Please log in and try again."
      open={isVisible}
      onCancel={dismiss}
      onAccept={goToLogin}
      acceptText="Go to Login"
    />
  )
}

export default AuthenticationAlert
