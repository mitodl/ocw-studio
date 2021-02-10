import incrementer from "./incrementer"

describe("incrementor", () => {
  it("increments", () => {
    const incr = incrementer()
    for (let counter = 1; counter < 10; ++counter) {
      expect(counter).toBe(incr.next().value)
    }
  })
})
