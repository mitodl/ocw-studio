import React from "react"
import { render, screen } from "@testing-library/react"
import { StudioListItem } from "./StudioList"

const mockUseLocationValue = {
  pathname: "/test/route",
  search: "",
  hash: "",
  state: null,
}

jest.mock("react-router", () => ({
  ...(jest.requireActual("react-router") as any),
  useLocation: jest.fn().mockImplementation(() => {
    return mockUseLocationValue
  }),
}))

describe("StudioListItem", () => {
  it("does not have hover-pointer class if onClick not provided", () => {
    render(<StudioListItem title="some-titlle" subtitle="meow" />)

    const listItem = screen.getByRole("listitem")
    expect(listItem).not.toHaveClass("hover-pointer")
  })

  it("does have hover-pointer class if onClick is provided", () => {
    render(
      <StudioListItem title="some-titlle" subtitle="meow" onClick={jest.fn} />,
    )

    const listItem = screen.getByRole("listitem")
    expect(listItem).toHaveClass("hover-pointer")
  })
})
