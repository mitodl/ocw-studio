import { turndownService } from "./turndown"

const turndownTest = (html: string, markdown: string) => {
  expect(turndownService.turndown(html)).toBe(markdown)
}

describe("turndown service", () => {
  it("should not add extra spaces to the beginning of a list item", () => {
    turndownTest("<ul><li>my item</li></ul>", "- my item")
  })

  it("should do the right thing with nested lists", () => {
    turndownTest(
      "<ul><li>first item<ul><li>nested item</li></ul></li></ul>",
      "- first item\n    - nested item"
    )
  })

  it("should correctly use rules defined for 'blank' tags", () => {
    // see the comment above the 'blankRule' code in ./turndown.ts
    // for an explanation of what this is testing
    turndownService.addRule("figureTest", {
      filter:      "figure",
      replacement: (): string => "This rule is being used"
    })
    turndownTest("<figure></figure>", "This rule is being used")
  })
})
