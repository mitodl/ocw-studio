import { editor } from "@ckeditor/ckeditor5-core"
import {
  SchemaContext,
  SchemaCompiledItemDefinition
} from "@ckeditor/ckeditor5-engine/src/model/schema"

// based on https://ckeditor.com/docs/ckeditor5/latest/features/table.html#disallow-nesting-tables
export default function DisallowNestedTables(editor: editor.Editor): void {
  editor.model.schema.addChildCheck(
    // @ts-ignore
    (
      context: SchemaContext,
      childDefinition: SchemaCompiledItemDefinition
    ): boolean | undefined => {
      if (
        childDefinition.name === "table" &&
        Array.from(context.getNames()).includes("table")
      ) {
        return false
      }
      return undefined
    }
  )
}
