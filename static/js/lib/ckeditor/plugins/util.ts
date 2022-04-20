import { pickBy } from "lodash"
import { TABLE_ALLOWED_ATTRS } from "./constants"
import { hasTruthyProp, isNotNil } from "../../../util"
import { ReplacementFunction } from "turndown"

/**
 * Given a string encased in quotes and in which all interior quote characters
 * are escaped, strip the encasing quotes and unescape the interior quotes.
 *
 * By default, the quotation character is a double quotation mark.
 * Use `singleQuotes=true` for single quotes. *The `singleQuotes` option is
 * currently unused on the frontend, but included for parity with the backend
 * version of this function.*
 */
export const unescapeStringQuotedWith = (
  text: string,
  singleQuotes = false
) => {
  const q = singleQuotes ? "'" : '"'

  const escapedQuoteRegex = new RegExp(
    [
      /(?<!\\)/.source, // anything except a backslash WITHOUT advancing match position
      /(\\\\)*\\/.source, // an odd number of backlsashes
      q // a quote
    ].join(""),
    "g"
  )

  const unescape: ReplacementFunction = (s: string) => {
    // s.replace is OK because there will be exactly one dbl quote in the match
    return s.replace(`\\${q}`, q)
  }

  const quoteCount = text.slice(1, -1).split(q).length - 1
  const escapedQuoteCount = text.match(escapedQuoteRegex)?.length ?? 0
  const allEscaped = quoteCount === escapedQuoteCount

  if (allEscaped && text.startsWith(q) && text.endsWith(q)) {
    return text.slice(1, -1).replace(escapedQuoteRegex, unescape)
  }
  throw new Error(`${text} is not a valid ${q}-quoted string`)
}

const ensureEncasedInQuotes = (text: string, singleQuotes = false) => {
  const q = singleQuotes ? "'" : '"'
  if (text.startsWith(q) && text.endsWith(q)) return text
  return q + text + q
}

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

export class ShortcodeParam {
  name?: string
  value: string

  constructor(value: string, name?: string) {
    this.name = name
    this.value = value
  }

  static hugoUnescapeParamValue(value: string) {
    const encased = ensureEncasedInQuotes(value)
    return unescapeStringQuotedWith(encased)
  }

  static hugoEscapeParamValue(value: string): string {
    return value.replace(/\n/g, " ").replace(/"/g, '\\"')
  }

  toHugo() {
    const hugoValue = `"${ShortcodeParam.hugoEscapeParamValue(this.value)}"`
    if (this.name) {
      return `${this.name}=${hugoValue}`
    }
    return hugoValue
  }
}

/**
 * Class to represent shortcodes. Includes some static methods to help create
 * shortcodes.
 *
 * Notes:
 *  - double quotes in shortcode parameter values are un-escaped for internal
 *  storage.
 */
export class Shortcode {
  name: string

  params: ShortcodeParam[]

  isPercentDelimited: boolean

  constructor(
    name: string,
    params: ShortcodeParam[],
    isPercentDelimited = false
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
   *
   * Re-escapes double quotes in parameter values
   */
  toHugo() {
    const stringifiedArgs = this.params.map(p => p.toHugo()).join(" ")
    const interior = `${this.name} ${stringifiedArgs}`
    if (this.isPercentDelimited) {
      return `{{% ${interior} %}}`
    }
    return `{{< ${interior} >}}`
  }

  /**
   * Regexp used for matching individual shortcode arguments.
   */
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

  /**
   * Convert a shortcode string to a Shortcode object.
   * @param s The shortcode as a string, e.g., `{{% resource_link "uuid" "text" %}}
   */
  static fromString(s: string): Shortcode {
    Shortcode.heuristicValidation(s)
    const isPercentDelmited = s.startsWith("{{%") && s.endsWith("%}}")
    const [nameMatch, ...argMatches] = s
      .slice(3, -3)
      .matchAll(Shortcode.ARG_REGEXP)
    const name = Shortcode.getArgMatchValue(nameMatch)
    const params = argMatches.map(match => {
      return new ShortcodeParam(
        Shortcode.getArgMatchValue(match),
        Shortcode.getArgMatchName(match)
      )
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
    const unescapedQuotes = s.match(/(?<!\\)(\\\\)*"/g)?.length ?? 0
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
    return ShortcodeParam.hugoUnescapeParamValue(
      match.groups.qvalue ?? match.groups.uvalue
    )
  }

  /**
   * Retrieve a shortcode parameter value by position or name.
   */
  get(param: number | string): string | undefined {
    if (typeof param === "number") {
      return this.params[param]?.value
    }
    return this.params.find(p => p.name === param)?.value
  }

  /**
   * Helper to create valid `{{< resource >}}` shortcodes.
   */
  static resource(
    uuid: string,
    { href, hrefUuid }: { href?: string | null; hrefUuid?: string | null } = {}
  ) {
    if (href && hrefUuid) {
      throw new Error("At most one of href, hrefUuid may be specified")
    }
    const name = "resource"
    const isPercentDelimited = false
    const params = [
      { name: "uuid", value: uuid },
      { name: "href", value: href },
      { name: "href_uuid", value: hrefUuid }
    ]
      .filter(hasTruthyProp("value"))
      .map(({ name, value }) => {
        return new ShortcodeParam(value, name)
      })
    return new Shortcode(name, params, isPercentDelimited)
  }

  static resourceLink(uuid: string, text: string, suffix?: string) {
    const name = "resource_link"
    const isPercentDelimited = true
    const paramValues = [uuid, text]
    if (suffix) {
      paramValues.push(`${suffix}`)
    }
    const params = paramValues.map(value => new ShortcodeParam(value))
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
