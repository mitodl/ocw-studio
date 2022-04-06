import { getExtensionName } from "."

describe("getExtensionName", () => {
  it.each([
    { path: "/bark/dog.pdf", ext: "pdf" },
    { path: "dog.pdf", ext: "pdf" },
    { path: "dog.woof.pdf", ext: "pdf" },
    { path: "dogwoof", ext: "" },
    { path: "/bark/dogwoof", ext: "" }
  ])("returns the file extension", ({ path, ext }) => {
    expect(getExtensionName(path)).toBe(ext)
  })
})
