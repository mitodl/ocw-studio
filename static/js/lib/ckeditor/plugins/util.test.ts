import { unescapeStringQuotedWith, Shortcode, ShortcodeParam } from "./util"

const makeParams = ({
  value,
  name
}: {
  value: string
  name?: string
}): ShortcodeParam => {
  return new ShortcodeParam(value, name)
}

describe("unescapeStringQuotedWith", () => {
  it.each([
    {
      escaped:   String.raw`"cats \"and\" 'dogs' are cool."`,
      unescaped: String.raw`cats "and" 'dogs' are cool.`
    },
    {
      escaped:   String.raw`"special characters « and backslashes \ \" are \ ok"`,
      unescaped: String.raw`special characters « and backslashes \ " are \ ok`
    },
    {
      escaped:   String.raw`"quotes are \" \\\" \\\\\" ok "`,
      unescaped: String.raw`quotes are " \\" \\\\" ok `
    },
    {
      escaped:   String.raw`"consecutive quotes are \"\" are OK"`,
      unescaped: String.raw`consecutive quotes are "" are OK`
    }
  ])("Unescapes interior quotes", ({ escaped, unescaped }) => {
    expect(unescapeStringQuotedWith(escaped)).toBe(unescaped)
  })

  it("Throws when the input is not encased in quotes", () => {
    expect(() => unescapeStringQuotedWith("cats")).toThrow(
      /not a valid "-quoted string/
    )
  })

  it("Throws when the input has unescaped interior quotes", () => {
    expect(() => unescapeStringQuotedWith('"ca"ts"')).toThrow(
      /not a valid "-quoted string/
    )
  })
})

describe("Shortcode", () => {
  describe("Shortcode.parse", () => {
    it("parses shortcodes with named params", () => {
      const text =
        '{{< some_shortcode cool_arg="cats and dogs" href_uuid=uuid456 >}}'
      const result = Shortcode.fromString(text)

      const params = [
        { name: "cool_arg", value: "cats and dogs" },
        { name: "href_uuid", value: "uuid456" }
      ].map(makeParams)
      expect(result).toStrictEqual(
        new Shortcode("some_shortcode", params, false)
      )
    })

    it("parses shortcodes with positional params", () => {
      const text = '{{< some_shortcode "cats and dogs" uuid456 >}}'
      const result = Shortcode.fromString(text)

      const params = [
        { name: undefined, value: "cats and dogs" },
        { name: undefined, value: "uuid456" }
      ].map(makeParams)
      expect(result).toStrictEqual(
        new Shortcode("some_shortcode", params, false)
      )
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
        ].map(makeParams)
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
        ].map(makeParams)
        expect(result).toStrictEqual(
          new Shortcode("my_shortcode", params, false)
        )
      }
    )

    it("unescapes quotes in the parameter value", () => {
      const text =
        '{{< some_shortcode "this has \\" escaped quotes" not_this "this \\"one\\" does" >}}'
      const result = Shortcode.fromString(text)
      const params = [
        { name: undefined, value: 'this has " escaped quotes' },
        { name: undefined, value: "not_this" },
        { name: undefined, value: 'this "one" does' }
      ].map(makeParams)
      expect(result).toStrictEqual(
        new Shortcode("some_shortcode", params, false)
      )
      expect(result.get(0)).toBe('this has " escaped quotes')
      expect(result.get(1)).toBe("not_this")
      expect(result.get(2)).toBe('this "one" does')
    })

    test("[BUG] issue if param values end in backslashes", () => {
      /**
       * The shortcode below is invalid (Hugo will error) but Shortcode.fromString
       * allows it. Do we care?
       */
      const text = '{{% resource_link uuid123 "ok \\\\" %}}'
      expect(Shortcode.fromString(text)).toStrictEqual(
        new Shortcode(
          "resource_link",
          [new ShortcodeParam("uuid123"), new ShortcodeParam("ok")],
          true
        )
      )
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

  describe("Shortcode.toHugo", () => {
    it("escapes quotes in named parameter values", () => {
      const shortcode = new Shortcode(
        "my_shortcode",
        [
          new ShortcodeParam('Cats "and" dogs', "first"),
          new ShortcodeParam(
            'special characters « and backslashes \\ " are \\ ok',
            "second_param"
          )
        ],
        false
      )
      expect(shortcode.toHugo()).toBe(
        '{{< my_shortcode first="Cats \\"and\\" dogs" second_param="special characters « and backslashes \\ \\" are \\ ok" >}}'
      )
    })

    it("escapes quotes in positional parameter values", () => {
      const shortcode = new Shortcode(
        "my_shortcode",
        [
          new ShortcodeParam('Cats "and" dogs'),
          new ShortcodeParam(
            'special characters « and backslashes \\ " are \\ ok'
          )
        ],
        false
      )
      expect(shortcode.toHugo()).toBe(
        '{{< my_shortcode "Cats \\"and\\" dogs" "special characters « and backslashes \\ \\" are \\ ok" >}}'
      )
    })

    it.each([
      {
        isPercentDelimited: false,
        expected:           '{{< my_shortcode first="some value" >}}'
      },
      {
        isPercentDelimited: true,
        expected:           '{{% my_shortcode first="some value" %}}'
      }
    ])(
      "uses percent delimiters when appropriate",
      ({ isPercentDelimited, expected }) => {
        const shortcode = new Shortcode(
          "my_shortcode",
          [new ShortcodeParam("some value", "first")],
          isPercentDelimited
        )
        expect(shortcode.toHugo()).toBe(expected)
      }
    )
  })

  describe("Shortcode.get", () => {
    it.each([
      '{{< my_shortcdoe catsmeow "dogs woof" >}}',
      '{{< my_shortcdoe zeroth=catsmeow first="dogs woof" >}}'
    ])("gets parameters by position", shortcodeText => {
      const shortcode = Shortcode.fromString(shortcodeText)
      expect(shortcode.get(0)).toBe("catsmeow")
      expect(shortcode.get(1)).toBe("dogs woof")
      expect(shortcode.get(2)).toBe(undefined)
    })

    it("gets parameters by name", () => {
      const shortcode = Shortcode.fromString(
        '{{< my_shortcdoe zeroth=catsmeow first="dogs woof" >}}'
      )
      expect(shortcode.get("zeroth")).toBe("catsmeow")
      expect(shortcode.get("first")).toBe("dogs woof")
      expect(shortcode.get("second")).toBe(undefined)
    })
  })

  describe("Shortcode.resource", () => {
    it.each([undefined, {}, { href: null }, { href: "" }])(
      "makes resources without href or href_uuid",
      options => {
        const shortcode = Shortcode.resource("bestuuidever", options)
        expect(shortcode).toStrictEqual(
          new Shortcode("resource", [
            new ShortcodeParam("bestuuidever", "uuid")
          ])
        )
      }
    )
    it("makes resources with href", () => {
      const shortcode = Shortcode.resource("bestuuidever", {
        href: "some_href"
      })
      expect(shortcode).toStrictEqual(
        new Shortcode("resource", [
          new ShortcodeParam("bestuuidever", "uuid"),
          new ShortcodeParam("some_href", "href")
        ])
      )
    })
    it("makes resources with hrefUuid", () => {
      const shortcode = Shortcode.resource("bestuuidever", {
        hrefUuid: "some_href_uuid"
      })
      expect(shortcode).toStrictEqual(
        new Shortcode("resource", [
          new ShortcodeParam("bestuuidever", "uuid"),
          new ShortcodeParam("some_href_uuid", "href_uuid")
        ])
      )
    })
    it("throws if both href and hrefUuid are provided", () => {
      expect(() =>
        Shortcode.resource("c", { hrefUuid: "b", href: "c" })
      ).toThrow(/At most one of href, hrefUuid/)
    })
  })

  describe("Shortcode.resourceLink", () => {
    it.each([
      {
        uuid:     "some-uuid",
        text:     "some text",
        suffix:   undefined,
        expected: '{{% resource_link "some-uuid" "some text" %}}'
      },
      {
        uuid:     "some-uuid",
        text:     "some text",
        suffix:   "",
        expected: '{{% resource_link "some-uuid" "some text" %}}'
      },
      {
        uuid:     "some-uuid",
        text:     'some "cool" text',
        suffix:   "?dog",
        expected:
          '{{% resource_link "some-uuid" "some \\"cool\\" text" "?dog" %}}'
      },
      {
        uuid:     "some-uuid",
        text:     "",
        suffix:   "#cat",
        expected: '{{% resource_link "some-uuid" "" "#cat" %}}'
      }
    ])("makes resource links", ({ uuid, text, suffix, expected }) => {
      const shortcode = Shortcode.resourceLink(uuid, text, suffix)
      expect(shortcode.toHugo()).toBe(expected)
    })
  })
})
