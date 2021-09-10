import Plugin from "@ckeditor/ckeditor5-core/src/plugin"
import Turndown from "turndown"
import Showdown from "showdown"
import { toWidget } from "@ckeditor/ckeditor5-widget/src/utils"
import { editor } from "@ckeditor/ckeditor5-core"
import Command from "@ckeditor/ckeditor5-core/src/command"

import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { TurndownRule } from "../../../types/ckeditor_markdown"
import {
  CKEDITOR_RESOURCE_UTILS,
  RenderResourceFunc,
  RESOURCE_LINK,
  RESOURCE_LINK_COMMAND
} from "./constants"

export const RESOURCE_LINK_SHORTCODE_REGEX = /{{< resource_link (\S+) >}}/g

const RESOURCE_LINK_CKEDITOR_CLASS = "resource-link"

const RESOURCE_LINK_ATTRIBUTE = "resourceUuid"

export function createResourceLinkElement( uuid: string, { writer }: any ) {
  // Priority 5 - https://github.com/ckeditor/ckeditor5-link/issues/121.
  const linkElement = writer.createAttributeElement( 'a', { uuid, class: RESOURCE_LINK_CKEDITOR_CLASS }, { priority: 5 } );
  writer.setCustomProperty( 'link', true, linkElement );

  return linkElement;
}

/**
 * Class for defining Markdown conversion rules for ResourceEmbed
 */
class ResourceLinkMarkdownSyntax extends MarkdownSyntaxPlugin {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  get showdownExtension() {
    return function resourceExtension(): Showdown.ShowdownExtension[] {
      return [
        {
          type:    "lang",
          regex:   RESOURCE_LINK_SHORTCODE_REGEX,
          replace: (_s: string, match: string) => {
            return `<span class="${RESOURCE_LINK_CKEDITOR_CLASS}" data-uuid="${match}"></span>`
          }
        }
      ]
    }
  }

  get turndownRule(): TurndownRule {
    return {
      name: RESOURCE_LINK,
      rule: {
        // TODO fix filter here
        filter:      "span",
        replacement: (_content: string, node: Turndown.Node): string => {
          // @ts-ignore
          const uuid = node.getAttribute("data-uuid")
          return `{{< resource_link ${uuid} >}}`
        }
      }
    }
  }
}

/**
 * A CKEditor Command for inserting a new ResourceEmbed (resourceEmbed)
 * node into the editor.
 */
class InsertResourceLinkCommand extends Command {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  execute(uuid: string) {
    const model = this.editor.model;
    const selection = model.document.selection;

    model.change( (writer: any) => {
      // If selection is collapsed then update selected link or insert new one at the place of caret.
      // if ( selection.isCollapsed ) {
      //   const position = selection.getFirstPosition();

      // When selection is inside text with `linkHref` attribute.
      // if ( selection.hasAttribute( 'linkHref' ) ) {
      //   // Then update `linkHref` value.
      //   const linkRange = findAttributeRange( position, 'linkHref', selection.getAttribute( 'linkHref' ), model );

      //   writer.setAttribute( 'linkHref', href, linkRange );

      //   truthyManualDecorators.forEach( item => {
      //     writer.setAttribute( item, true, linkRange );
      //   } );

      //   falsyManualDecorators.forEach( item => {
      //     writer.removeAttribute( item, linkRange );
      //   } );

      //   // Put the selection at the end of the updated link.
      //   writer.setSelection( writer.createPositionAfter( linkRange.end.nodeBefore ) );
      // }
      // // If not then insert text node with `linkHref` attribute in place of caret.
      // // However, since selection is collapsed, attribute value will be used as data for text node.
      // // So, if `href` is empty, do not create text node.
      // else if ( href !== '' ) {
      //   const attributes = toMap( selection.getAttributes() );

      //   attributes.set( 'linkHref', href );

      //   truthyManualDecorators.forEach( item => {
      //     attributes.set( item, true );
      //   } );

      //   const { end: positionAfter } = model.insertContent( writer.createText( href, attributes ), position );

      //   // Put the selection at the end of the inserted link.
      //   // Using end of range returned from insertContent in case nodes with the same attributes got merged.
      //   writer.setSelection( positionAfter );
      // }

      // // Remove the `linkHref` attribute and all link decorators from the selection.
      // // It stops adding a new content into the link element.
      // [ 'linkHref', ...truthyManualDecorators, ...falsyManualDecorators ].forEach( item => {
      //   writer.removeSelectionAttribute( item );
      // } );
      // } else {
      // If selection has non-collapsed ranges, we change attribute on nodes inside those ranges
      // omitting nodes where the `linkHref` attribute is disallowed.
      const ranges = model.schema.getValidRanges( selection.getRanges(), 'linkHref' );

      // But for the first, check whether the `linkHref` attribute is allowed on selected blocks (e.g. the "image" element).
      const allowedRanges = [];

      for ( const element of selection.getSelectedBlocks() ) {
        if ( model.schema.checkAttribute( element, RESOURCE_LINK_ATTRIBUTE ) ) {
          allowedRanges.push( writer.createRangeOn( element ) );
        }
      }

      // Ranges that accept the `linkHref` attribute. Since we will iterate over `allowedRanges`, let's clone it.
      const rangesToUpdate = allowedRanges.slice();

      // For all selection ranges we want to check whether given range is inside an element that accepts the `linkHref` attribute.
      // If so, we don't want to propagate applying the attribute to its children.
      for ( const range of ranges ) {
        if ( this._isRangeToUpdate( range, allowedRanges ) ) {
          rangesToUpdate.push( range );
        }
      }

      for ( const range of rangesToUpdate ) {
        writer.setAttribute( RESOURCE_LINK_ATTRIBUTE, uuid, range );
      }
      // }
    });


    // this.editor.model.change((writer: any) => {
    //   const link = writer.createElement(RESOURCE_LINK, { uuid })
    //   this.editor.model.insertContent(link)
    // })
  }

  //   refresh() {
  //     const model = this.editor.model
  //     const selection = model.document.selection
  //     const allowedIn = model.schema.findAllowedParent(
  //       selection.getFirstPosition(),
  //       RESOURCE_LINK
  //     )
  //     this.isEnabled = allowedIn !== null
  //   }
  _isRangeToUpdate( range: any, allowedRanges: any) {
    for ( const allowedRange of allowedRanges ) {
      // A range is inside an element that will have the `linkHref` attribute. Do not modify its nodes.
      if ( allowedRange.containsRange( range ) ) {
        return false;
      }
    }

    return true;
  }
}

/**
 * The main 'editing' plugin for Resource Links. This basically
 * adds the node type to the schema and sets up all the serialization/
 * deserialization rules for it.
 */
class ResourceLinkEditing extends Plugin {
  constructor(editor: editor.Editor) {
    super(editor)
  }

  init() {
    this._defineSchema()
    this._defineConverters()

    this.editor.commands.add(
      RESOURCE_LINK_COMMAND,
      new InsertResourceLinkCommand(this.editor)
    )
  }

  _defineSchema() {
    const schema = this.editor.model.schema

    // schema.register(RESOURCE_LINK, {
    //   isObject:        true,
    //   isInline:        true,
    //   isBlock:         false,
    //   allowIn:         ["$root", "$block"],
    //   allowAttributes: ["uuid"]
    // })

    schema.extend( '$text', { allowAttributes: RESOURCE_LINK_ATTRIBUTE } );
  }

  _defineConverters() {
    const conversion = this.editor.conversion

    /**
     * convert HTML string to a view element (i.e. ckeditor
     * internal state, *not* to a DOM element)
     */
    // conversion.for("upcast").elementToElement({
    //   view: {
    //     name:  "span",
    //     class: RESOURCE_LINK_CKEDITOR_CLASS
    //   },

    //   model: (viewElement: any, { writer: modelWriter }: any) => {
    //     return modelWriter.createElement(RESOURCE_LINK, {
    //       uuid: viewElement.getAttribute("data-uuid")
    //     })
    //   }
    // })

    conversion.for( 'upcast' )
      .elementToAttribute( {
        view: {
          name: 'a',
          attributes: {
            uuid: true,
            class: RESOURCE_LINK_CKEDITOR_CLASS
          }
        },
        model: {
          key: RESOURCE_LINK,
          value: (viewElement: any) => viewElement.getAttribute( RESOURCE_LINK_ATTRIBUTE )
        }
      } );

      /**
       * converts view element to HTML element for data output
       */
      // conversion.for("dataDowncast").elementToElement({
      //   model: RESOURCE_LINK,
      //   view:  (modelElement: any, { writer: viewWriter }: any) => {
      //     return viewWriter.createEmptyElement("span", {
      //       "data-uuid": modelElement.getAttribute("uuid"),
      //       class:       RESOURCE_LINK_CKEDITOR_CLASS
      //     })
      //   }
      // })

      conversion.for( 'dataDowncast' )
        .attributeToElement( { model: RESOURCE_LINK, view: createResourceLinkElement } );


      const renderResource: RenderResourceFunc = (
        this.editor.config.get(CKEDITOR_RESOURCE_UTILS) ?? {}
      ).renderResource

      /**
       * editingDowncast converts a view element to HTML which is actually shown
       * in the editor for WYSIWYG purposes
       * (for the youtube embed this is an iframe)
       */
      // conversion.for("editingDowncast").elementToElement({
      //   model: RESOURCE_LINK,
      //   view:  (modelElement: any, { writer: viewWriter }: any) => {
      //     const uuid = modelElement.getAttribute("uuid")

      //     const span = viewWriter.createContainerElement("span", {
      //       class: RESOURCE_LINK_CKEDITOR_CLASS
      //     })

      //     const reactWrapper = viewWriter.createRawElement(
      //       "span",
      //       {
      //         class: "resource-react-wrapper"
      //       },
      //       function(el: HTMLElement) {
      //         if (renderResource) {
      //           renderResource(uuid, el, RESOURCE_LINK)
      //         }
      //       }
      //     )

      //     viewWriter.insert(viewWriter.createPositionAt(span, 0), reactWrapper)

      //     return toWidget(span, viewWriter, { label: "Resource Link" })
      //   }
      // })

      conversion.for( 'editingDowncast' )
        .attributeToElement( { model: RESOURCE_LINK, view: createResourceLinkElement })

  }
}

/**
 * CKEditor plugin that provides functionality to link to resource records
 * in the editor. These are rendered to Markdown as `{{< resource_link UUID >}}`
 * shortcodes.
 */
export default class ResourceLink extends Plugin {
  static get pluginName(): string {
    return "ResourceLink"
  }

  static get requires(): Plugin[] {
    // this return value here is throwing a type error that I don't understand,
    // since very similar code in MarkdownMediaEmbed.ts is fine
    //
    // Anyhow, since I have not diagnosed it and since things seem to
    // be running fine I'm going to just ignore for now.
    return [
      // @ts-ignore
      ResourceLinkEditing,
      // @ts-ignore
      ResourceLinkMarkdownSyntax
    ]
  }
}
