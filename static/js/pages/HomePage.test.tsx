import * as React from "react"
import { shallow } from "enzyme"

import HomePage from "./HomePage"

describe("HomePage", () => {
  it("shows the Touchstone login button if the user is logged out", () => {
    SETTINGS.user = null
    const wrapper = shallow(<HomePage />)
    const link = wrapper.find("a[href='/login/saml/?idp=default']")
    expect(link.exists()).toBeTruthy()
    expect(link.text()).toBe("Login with MIT Touchstone")
  })

  it("hides the Touchstone login button if the user is logged in", () => {
    const wrapper = shallow(<HomePage />)
    const link = wrapper.find("a[href='/login/saml/?idp=default']")
    expect(link.exists()).toBeFalsy()
  })
})
