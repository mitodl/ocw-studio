import { pickBy } from "lodash"
import { TABLE_ALLOWED_ATTRS } from "./constants"
import { hasNotNilProp, isNotNil } from "../../../util"

export function buildAttrsString(attrs: RegExpMatchArray | null): string {
  return attrs ?
    attrs
      .map(attr =>
        TABLE_ALLOWED_ATTRS.some(allowedAttr => attr.includes(allowedAttr)) ?
          ` ${attr}` :
          ""
      )
      .join("") :
    ""
}

interface ShortcodeArg {
  name?: string
  value: string
}

/**
 * Class to represent shortcodes. Includes some static methods to help create
 * shortcodes.
 */
export class Shortcode {
  name: string

  params: ShortcodeArg[]

  isPercentDelimited: boolean

  constructor(
    name: string,
    params: ShortcodeArg[],
    isPercentDelimited: boolean
  ) {
    this.name = name
    this.params = params
    this.isPercentDelimited = isPercentDelimited

    const hasPositionalParams = params.some(p => p.name === undefined)
    const hasNamedParams = params.some(p => p.name !== undefined)
    if (hasNamedParams && hasPositionalParams) {
      throw new Error(
        "Invalid Shortcode: Cannot mix named and positional parameters"
      )
    }
  }

  /**
   * Convert this shortcode to Hugo markdown.
   */
  toHugo() {
    const stringifiedArgs = this.params
      .filter(({ value }) => value)
      .map(({ name, value }) => {
        return name ? `${name}="${value}"` : `"${value}"`
      })
      .join(" ")
    const interior = `${this.name} ${stringifiedArgs}`
    if (this.isPercentDelimited) {
      return `{{% ${interior} %}}`
    }
    return `{{< ${interior} >}}`
  }

  private static ARG_REGEXP = new RegExp(
    [
      /((?<name>[a-zA-Z_]+)=)?/.source,
      "(",
      /("(?<qvalue>.*?)(?<!\\)")/.source,
      "|",
      /((?<uvalue>[^"\s=]+?)\s)/.source,
      ")"
    ].join(""),
    "g"
  )

  static fromString(s: string) {
    Shortcode.heuristicValidation(s)
    const isPercentDelmited = s.startsWith("{{%") && s.endsWith("%}}")
    const [nameMatch, ...argMatches] = s
      .slice(3, -3)
      .matchAll(Shortcode.ARG_REGEXP)
    const name = Shortcode.getArgMatchValue(nameMatch)
    const params = argMatches.map(match => {
      return {
        name:  Shortcode.getArgMatchName(match),
        value: Shortcode.getArgMatchValue(match)
      }
    })

    return new Shortcode(name, params, isPercentDelmited)
  }

  /**
   * Validate that `s` seems like a reasonable shortcode. This does not
   * guarantee that `s` is a valid shortcode, but will at least reject known
   * tricky cases that could arise from ocw data.
   *
   * Most of our shortcode recognition is done via regex, caputring conent
   * between "{{<" and ">}}" (or the percent-delimited variant). Such regexes
   * generally work very well, except in a few circumstances where we
   * inadvertently have shortcodes inside shortcodes. For example:
   *
   *  {{< image-gallery-item ... text="Botryoidal and massive hematite: Fe{{< sub 2 >}}O{{< sub 3 >}}." >}}
   *
   * In this case, a regex might incorrectly identify "...sub 2 >}}" as the end
   * of the shortcode. This function would reject in such a case.
   */
  private static heuristicValidation(s: string) {
    const isPercentDelmited = s.startsWith("{{%") && s.endsWith("%}}")
    const isAngleDelimited = s.startsWith("{{<") && s.endsWith(">}}")
    if (!isPercentDelmited && !isAngleDelimited) {
      throw new Error(
        `${s} is not a valid shortcode: should start/end with matching delimiters`
      )
    }
    const delimiters = ["{{<", ">}}", "{{%", "%}}"]
    if (delimiters.some(d => s.slice(3, -3).includes(d))) {
      throw new Error(
        `Shortcode ${s} is invalid: content includes shortcode delimiters.`
      )
    }
    const unescapedQuotes = s.match(/(?<!\\)"/g)?.length ?? 0
    if (unescapedQuotes % 2 > 0) {
      throw new Error(
        `Shortcode ${s} is invalid: odd number of unescaped quotes.`
      )
    }
  }

  private static getArgMatchName(match: RegExpMatchArray): string {
    if (match.groups === undefined) {
      throw new Error("Expected groups to be defined.")
    }
    return match.groups.name
  }

  private static getArgMatchValue(match: RegExpMatchArray): string {
    if (match.groups === undefined) {
      throw new Error("Expected groups to be defined.")
    }
    return match.groups.qvalue ?? match.groups.uvalue
  }

  /**
   * Retrieve a shortcode parameter value by position or name.
   */
  get(param: number | string): string | undefined {
    if (typeof param === "number") {
      return this.params[0].value
    }
    return this.params.find(p => p.name === param)?.value
  }

  /**
   * Helper to create valid `{{< resource >}}` shortcodes.
   */
  static resource(
    uuid: string,
    { href, hrefUuid }: { href?: string | null; hrefUuid?: string | null }
  ) {
    const name = "resource"
    const isPercentDelimited = false
    const params = [
      { name: "uuid", value: uuid },
      { name: "href", value: href },
      { name: "href_uuid", value: hrefUuid }
    ].filter(hasNotNilProp("value"))
    return new Shortcode(name, params, isPercentDelimited)
  }
}

/**
 * Write the HTML string for a tag name and attributes. For example:
 * ```ts
 * makeHtmlString('div', {'data-uuid': 'uuid123', meow: undefined, bark: 'woof' })
 * // <div bark="woof" data-uuid="uuid123"></div>
 * ```
 *
 * Does NOT perform any HTML escaping on the attribute values.
 */
export const makeHtmlString = (
  tagName: string,
  attributes: Record<string, string | undefined>
) => {
  const attrs = pickBy(attributes, isNotNil)
  const attrAssignments = Object.keys(attrs)
    .sort()
    .map(attrName => {
      return `${attrName}="${attrs[attrName]}"`
    })
  return `<${tagName} ${attrAssignments.join(" ")}></${tagName}>`
}
