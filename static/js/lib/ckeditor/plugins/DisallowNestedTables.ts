import { Editor } from "@ckeditor/ckeditor5-core"
import {
  SchemaContext,
  SchemaCompiledItemDefinition
} from "@ckeditor/ckeditor5-engine/src/model/schema"

// based on https://ckeditor.com/docs/ckeditor5/latest/features/table.html#disallow-nesting-tables
export default function DisallowNestedTables(editor: Editor): void {
  editor.model.schema.addChildCheck(
    // @ts-expect-error The CKEditor docs return undefined in the check, maybe their types are wrong?
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
