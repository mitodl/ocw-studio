import React, { ReactNode } from "react"

interface ErrorComponentProps {
  children?: string | ReactNode | null | undefined
}

export const FormError: React.FunctionComponent = (
  props: ErrorComponentProps
) => {
  return props.children ? (
    <div className="form-error">{props.children}</div>
  ) : null
}
