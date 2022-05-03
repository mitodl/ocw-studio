import { createSlice, PayloadAction } from "@reduxjs/toolkit"
import { User } from "../../types/user"

interface UserState {
  user: User | null
  hasSessionExpired: boolean
}

const initialState: UserState = {
  /**
   * SETTINGS.user does exist and comes from django.
   * This should be the only usage in our app. All other usage of `user` should
   * refer to the store. SETTINGS.user is intentionally untyped to promote using
   * the store value.
   */
  // @ts-expect-error intentially untyped
  user:              SETTINGS.user,
  hasSessionExpired: false
}

const userSlice = createSlice({
  name:     "user",
  initialState,
  reducers: {
    setUser(state, action: PayloadAction<User>) {
      state.user = action.payload
    },
    setExpired(state) {
      state.hasSessionExpired = true
    },
    clearUser(state) {
      state.user = null
      state.hasSessionExpired = false
    }
  }
})

export const { setExpired, setUser, clearUser } = userSlice.actions
export default userSlice
