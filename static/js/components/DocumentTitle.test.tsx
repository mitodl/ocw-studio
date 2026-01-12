import DocumentTitle, { formatTitle } from "./DocumentTitle"
import { render } from "@testing-library/react"
import React from "react"

describe("DocumentTitle component", () => {
  const renderComponent = (title: string) =>
    render(<DocumentTitle title={title} />)

  it("formatTitle should format titles correctly", () => {
    expect(formatTitle()).toBe("OCW Studio")
    expect(formatTitle("Site Page")).toBe("OCW Studio | Site Page")
    expect(formatTitle("Site Page", "Edit")).toBe(
      "OCW Studio | Site Page | Edit",
    )
  })

  it("should mount and set the title", () => {
    renderComponent("test title")
    expect(document.title).toBe("test title")
  })
})
