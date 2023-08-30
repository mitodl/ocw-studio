import { SchemaContext } from "@ckeditor/ckeditor5-engine/src/model/schema"

/**
 * Adds a check that can disallow the given attribute in the current context.
 * This check is in addition to any default checks performed by the existing
 * schema definition.
 *
 * See [CKEditor docs](https://ckeditor.com/docs/ckeditor5/latest/api/module_engine_model_schema-Schema.html#function-addAttributeCheck)
 * for more details.
 */
type AttributeCheckFunction = (
  context: SchemaContext,
  attributeName: string,
) => boolean | undefined

const someItemHasAttribute = (
  context: SchemaContext,
  attributeName: string,
): boolean => {
  for (const item of context) {
    for (const attribute of item.getAttributeKeys()) {
      if (attribute === attributeName) {
        return true
      }
    }
  }
  return false
}

const makeCheckNothBoth = (
  attrName1: string,
  attrName2: string,
): AttributeCheckFunction => {
  return (context, attributeName) => {
    if (!context.endsWith("$text")) return undefined
    if (attributeName === attrName1) {
      return !someItemHasAttribute(context, attrName2)
    }
    if (attributeName === attrName2) {
      return !someItemHasAttribute(context, attrName1)
    }
    return undefined
  }
}

const checkNotSubAndSup = makeCheckNothBoth("subscript", "superscript")

export { checkNotSubAndSup }
