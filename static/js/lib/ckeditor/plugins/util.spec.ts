import { Shortcode } from "./util"

describe("Shortcode", () => {
  describe("Shortcode.parse", () => {
    it("parses shortcodes with named params", () => {
      const text =
        '{{< some_shortcode cool_arg="cats and dogs" href_uuid=uuid456 >}}'
      const result = Shortcode.fromString(text)

      const args = [
        { name: "cool_arg", value: "cats and dogs" },
        { name: "href_uuid", value: "uuid456" }
      ]
      expect(result).toStrictEqual(new Shortcode("some_shortcode", args, false))
    })

    it("parses shortcodes with positional params", () => {
      const text = '{{< some_shortcode "cats and dogs" uuid456 >}}'
      const result = Shortcode.fromString(text)

      const args = [
        { name: undefined, value: "cats and dogs" },
        { name: undefined, value: "uuid456" }
      ]
      expect(result).toStrictEqual(new Shortcode("some_shortcode", args, false))
    })

    it.each([
      '{{< my_shortcode "must have quotes" can_have_quotes >}}',
      '{{< my_shortcode "must have quotes" "can_have_quotes" >}}'
    ])(
      "tolerates but does not require quotes around values without spaces for positional params",
      text => {
        const result = Shortcode.fromString(text)
        const params = [
          { name: undefined, value: "must have quotes" },
          { name: undefined, value: "can_have_quotes" }
        ]
        expect(result).toStrictEqual(
          new Shortcode("my_shortcode", params, false)
        )
      }
    )

    it.each([
      '{{< my_shortcode abc="must have quotes" xyz=can_have_quotes >}}',
      '{{< my_shortcode abc="must have quotes" xyz="can_have_quotes" >}}'
    ])(
      "tolerates but does not require quotes around values without spaces for named params",
      text => {
        const result = Shortcode.fromString(text)
        const params = [
          { name: "abc", value: "must have quotes" },
          { name: "xyz", value: "can_have_quotes" }
        ]
        expect(result).toStrictEqual(
          new Shortcode("my_shortcode", params, false)
        )
      }
    )

    it("allows quotes inside the argument values", () => {
      const text =
        '{{< some_shortcode "this has \\" escaped quotes" not_this "this \\"one\\" does" >}}'
      const result = Shortcode.fromString(text)
      const args = [
        { name: undefined, value: 'this has \\" escaped quotes' },
        { name: undefined, value: "not_this" },
        { name: undefined, value: 'this \\"one\\" does' }
      ]
      expect(result).toStrictEqual(new Shortcode("some_shortcode", args, false))
    })

    it("throws error if content includes shortcode delimiter", () => {
      const text = '{{< old_resource_link uuid123 "H{{< sub 2 >}}'
      expect(() => Shortcode.fromString(text)).toThrow(
        /includes shortcode delimiter/
      )
    })

    it("throws error if content includes odd number of unescaped quotes", () => {
      const text = '{{< old_resource_link uuid123 "cat\\"" " >}}'
      expect(() => Shortcode.fromString(text)).toThrow(
        /odd number of unescaped quotes/
      )
    })

    it.each([
      "{{< some_shortcode uuid123",
      "{{< some_shortcode uuid123 %}}",
      "some_shortcode uuid123 %}}",
      "{{% some_shortcode uuid123 >}}"
    ])(
      "throws error if shortcode does not start and end with matching delimiters",
      text => {
        expect(() => Shortcode.fromString(text)).toThrow(/matching delimiters/)
      }
    )
  })

  it("does not allow mixing named and positional params", () => {
    const text = '{{< resource uuid123 href_uuid="uuid456" >}}'
    expect(() => Shortcode.fromString(text)).toThrow(
      /Cannot mix named and positional/
    )
  })

  describe('Shortcode.get', () => {
    it.each([
      '{{< my_shortcdoe catsmeow "dogs woof" >}}',
      '{{< my_shortcdoe zeroth=catsmeow first="dogs woof" >}}'
    ])('gets parameters by position', shortcodeText => {
      const shortcode = Shortcode.fromString(shortcodeText)
      expect(shortcode.get(0)).toBe("catsmeow")
      expect(shortcode.get(1)).toBe("dogs woof")
      expect(shortcode.get(2)).toBe(undefined)
    })

    it('gets parameters by name', () => {
      const shortcode = Shortcode.fromString('{{< my_shortcdoe zeroth=catsmeow first="dogs woof" >}}')
      expect(shortcode.get("zeroth")).toBe("catsmeow")
      expect(shortcode.get("first")).toBe("dogs woof")
      expect(shortcode.get("second")).toBe(undefined)
    })
  })
})
