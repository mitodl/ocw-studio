import { TABLE_ELS } from "./plugins/constants"
import { ruleMatches, turndownService } from "./turndown"

const turndownTest = (html: string, markdown: string) => {
  expect(turndownService.turndown(html)).toEqual(markdown)
}

describe("turndown service", () => {
  it("should not add extra spaces to the beginning of a list item", () => {
    turndownTest("<ul><li>my item</li></ul>", "- my item")
  })

  it("should do the right thing with nested lists", () => {
    turndownTest(
      "<ul><li>first item<ul><li>nested item</li></ul></li></ul>",
      "- first item\n    - nested item",
    )
  })

  it("should correctly use rules defined for 'blank' tags", () => {
    // see the comment above the 'blankRule' code in ./turndown.ts
    // for an explanation of what this is testing
    turndownService.addRule("figureTest", {
      filter: "figure",
      replacement: (): string => "This rule is being used",
    })
    turndownTest("<figure></figure>", "This rule is being used")
  })

  it("supports a two-item list", () => {
    turndownTest(
      "<ul><li>first item</li><li>second item</li></ul>",
      "- first item\n- second item",
    )
  })

  // regression test for the bug documented in
  // https://github.com/mitodl/ocw-studio/issues/113
  it("shouldn't blow up if there's an empty list item", () => {
    turndownTest("<ul><li>first item</li><li></li></ul>", "- first item\n-")
  })

  it("should override any rules that match table elements", () => {
    expect(
      turndownService.rules.array.filter((rule) =>
        TABLE_ELS.some((el) => {
          const element = document.createElement(el)
          document.body.appendChild(element)
          return ruleMatches(rule, element)
        }),
      ),
    ).toStrictEqual([])
  })
})
