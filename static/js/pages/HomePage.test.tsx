import * as React from "react"
import { shallow } from "enzyme"

import HomePage from "./HomePage"

describe("HomePage", () => {
  it("shows a Touchstone login button", () => {
    const wrapper = shallow(<HomePage />)
    const link = wrapper.find("a")
    expect(link.text()).toBe("Login with MIT Touchstone")
    expect(link.prop("href")).toBe("/login/saml/?idp=default")
  })
})
