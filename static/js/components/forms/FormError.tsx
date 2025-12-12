import React, { ReactNode } from "react"

interface ErrorComponentProps {
  children?: string | ReactNode | null | undefined
}

export const FormError: React.FunctionComponent<ErrorComponentProps> = (
  props,
) => {
  return props.children ? (
    <div className="form-error">{props.children}</div>
  ) : null
}
