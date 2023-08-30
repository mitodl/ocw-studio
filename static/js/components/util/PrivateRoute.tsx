import React from "react"
import { Route, RouteProps, Redirect } from "react-router"
import { useAppSelector } from "../../hooks/redux"
import { loginUrl } from "../../lib/urls"

function PrivateRoute({ children, ...rest }: RouteProps): React.ReactElement {
  const { user } = useAppSelector((state) => state.user)

  return (
    <Route
      {...rest}
      render={() => {
        return user ? children : <Redirect to={loginUrl.toString()} />
      }}
    />
  )
}

export default PrivateRoute
