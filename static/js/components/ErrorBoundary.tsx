import * as Sentry from "@sentry/react"
import React from "react"

const Fallback = () => (
  <div>An error has occurred. Please reload your page.</div>
)

const ErrorBoundary: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  return (
    <Sentry.ErrorBoundary fallback={<Fallback />}>
      {children}
    </Sentry.ErrorBoundary>
  )
}

export default ErrorBoundary
