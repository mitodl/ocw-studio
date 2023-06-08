import { createSlice, PayloadAction } from "@reduxjs/toolkit"
import { User } from "../../types/user"

interface UserState {
  user: User | null
  authenticationErrors: number
}

const initialState: UserState = {
  /**
   * SETTINGS.user does exist and comes from django.
   * This should be the only usage in our app. All other usage of `user` should
   * refer to the store. SETTINGS.user is intentionally untyped to promote using
   * the store value.
   */
  // @ts-expect-error intentially untyped
  user:                 SETTINGS.user,
  /**
   * How many authentication errors has this user experienced?
   *
   * This is a counter in order to re-show the login prompt if it was previously
   * dismissed and the user experiences another auth error.
   */
  authenticationErrors: 0
}

const userSlice = createSlice({
  name:     "user",
  initialState,
  reducers: {
    setUser(state, action: PayloadAction<User>) {
      state.user = action.payload
    },
    incrementAuthenticationErrors(state) {
      state.authenticationErrors += 1
    },
    clearUser(state) {
      state.user = null
      state.authenticationErrors = 0
    }
  }
})

export const { setUser, clearUser, incrementAuthenticationErrors } =
  userSlice.actions
export default userSlice
