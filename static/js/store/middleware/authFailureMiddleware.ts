import { Middleware } from "redux"
import { ReduxState, AppDispatch } from "../rootReducer"
import { actionTypes, RequestFailureAction } from "redux-query"
import { incrementAuthenticationErrors } from "../user"

const failures = [actionTypes.REQUEST_FAILURE, actionTypes.MUTATE_FAILURE]

type AppMiddleware = Middleware<unknown, ReduxState, AppDispatch>

/**
 * Checks whether a redux-query response action is an authentication error.
 * Authentication errors are either
 *  1. status code 401
 *  2. status code 403 with a specific message detail
 *
 * Our current Django setup only ever returns 403 as Authentication errors.
 * See https://www.django-rest-framework.org/api-guide/authentication/#sessionauthentication
 */
const isAuthenticationError = (response: RequestFailureAction): boolean => {
  if (response.status === 401) return true
  if (response.status === 403) {
    return (
      response.responseBody.detail ===
      "Authentication credentials were not provided."
    )
  }
  return false
}

/**
 * Middleware that increments the `user.authenicationErrors` when redux-query
 * returns authentication errors.
 */
const authFailureMiddleware: AppMiddleware = store => next => action => {
  if (failures.includes(action.type) && isAuthenticationError(action)) {
    store.dispatch(incrementAuthenticationErrors())
  }
  return next(action)
}

export default authFailureMiddleware
