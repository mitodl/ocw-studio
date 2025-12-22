import React from "react"
import { Route, RouteProps, Redirect } from "react-router"
import { useAppSelector } from "../../hooks/redux"
import { loginUrl } from "../../lib/urls"

interface PrivateRouteProps extends Omit<RouteProps, "children"> {
  children: React.ReactNode
}

function PrivateRoute({
  children,
  ...rest
}: PrivateRouteProps): React.ReactElement {
  const { user } = useAppSelector((state) => state.user)

  return (
    <Route
      {...rest}
      render={() => (user ? children : <Redirect to={loginUrl.toString()} />)}
    />
  )
}

export default PrivateRoute
