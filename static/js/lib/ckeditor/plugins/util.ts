import { TABLE_ALLOWED_ATTRS } from "./constants"

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
