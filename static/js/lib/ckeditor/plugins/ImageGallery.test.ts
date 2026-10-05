import EssentialsPlugin from "@ckeditor/ckeditor5-essentials/src/essentials"
import Paragraph from "@ckeditor/ckeditor5-paragraph/src/paragraph"

import ImageGallery from "./ImageGallery"
import Markdown from "./Markdown"
import { createTestEditor } from "./test_util"
import {
  ADD_IMAGE_GALLERY,
  CKEDITOR_RESOURCE_UTILS,
  ImageGalleryHandle,
} from "./constants"
import { buildGalleryItem } from "./galleryItems"
import { makeWebsiteContentDetail } from "../../../util/factories/websites"

/**
 * Every test goes through setData/getData, as the editor does. A gallery's
 * Markdown is only rebuilt from the editor's own saved HTML, so converting
 * hand-written HTML would not exercise the real path.
 */
const NBSP = "\u00a0"

let handles: ImageGalleryHandle[] = []
const resourceUtils = {
  [CKEDITOR_RESOURCE_UTILS]: {
    renderImageGallery: (_el: HTMLElement, handle: ImageGalleryHandle) => {
      handles.push(handle)
    },
  },
}
const getEditor = createTestEditor(
  [Paragraph, ImageGallery, Markdown],
  resourceUtils,
)
const getEditorWithUndo = createTestEditor(
  [EssentialsPlugin, Paragraph, ImageGallery, Markdown],
  resourceUtils,
)

const PRODUCTION_GALLERY = [
  '{{< image-gallery id="788b6153-ce75-e1be-31f0-a394ce761f32_nanogallery2" baseUrl="/courses/18-05-introduction-to-probability-and-statistics-spring-2014/" >}}',
  String.raw`{{< image-gallery-item href="6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg" data-ngdesc="" text="The walls of our {{% resource_link \"c2956690-7ead-4f56-8282-fe998b987b00\" \"TEAL classroom\" %}} are lined with whiteboards." >}}`,
  '{{< image-gallery-item uuid="0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21" href="ffd3fea2cf932a2072579f1182251e33_staurolite.jpg" data-ngdesc="Staurolite" text="Staurolite: Fe{{< sub 2 >}}Al{{< sub 9 >}}Si{{< sub 4 >}}" >}}',
  "{{</ image-gallery >}}",
].join("\n")

/**
 * Real gallery items from production pages, cut short where they are long, one
 * given a uuid as the image_gallery_item_uuid cleanup writes them and one given
 * extra typography. Each carries something a careless conversion would
 * rewrite: links with escaped quotes, chained sub shortcodes, the Markdown
 * escapes `\-`, `\[` and `\<`, an HTML entity, paragraph breaks already
 * flattened to two spaces, and non-ASCII text.
 */
const REAL_ITEMS = [
  String.raw`{{< image-gallery-item href="ffd3fea2cf932a2072579f1182251e33_Image1.jpg" data-ngdesc="An end view diagram of the Beaver press with various parts identified." text="{{% resource_link \"d625c74d-9975-490c-809c-f5593c583cce\" \"Spindle\" %}} - The screw to which the bar of the press is affixed, and which produces the pressure on the platen.  {{% resource_link \"29d9b919-b219-477b-b2b8-6c769c096c29\" \"Head\" %}} - That part of a wooden press in which the nut of the spindle is fixed.  Nut  {{% resource_link \"f59f5e78-da35-4e61-a40a-92d1f77c70fe\" \"Till, or Shelf\" %}} - A mahogany shelf." >}}`,
  String.raw`{{< image-gallery-item uuid="0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21" href="de985c458b203ed262dfdcfe5109c400_lab2-16.jpg" data-ngdesc="Vesuvianite: Ca10(Mg,Fe)2Al4(SiO4)5(Si2O7)2(OH)4. Courtesy of OCW." text="Vesuvianite: Ca{{< sub 10 >}}(Mg,Fe){{< sub 2 >}}Al{{< sub 4 >}}(SiO{{< sub 4 >}}){{< sub 5 >}}(Si{{< sub 2 >}}O{{< sub 7 >}}){{< sub 2 >}}(OH){{< sub 4 >}}." >}}`,
  String.raw`{{< image-gallery-item href="328fb82d2a9b2a07c3f9dab9bb5a7367_lab4-4.jpg" data-ngdesc="Gypsum twins: CaSO4-2H2O. Courtesy of OCW." text="Gypsum twins: CaSO{{< sub 4 >}}\-2H{{< sub 2 >}}O." >}}`,
  String.raw`{{< image-gallery-item href="bc98f2fa0fbb25da8e34ff3647b2879e_1073.jpeg" data-ngdesc="Dar al-&grave;Adl as represented by Robert Hay in his Illustrations of Cairo (1840)." text="Dar al-&grave;Adl as represented by Robert Hay in his Illustrations of Cairo (1840)." >}}`,
  String.raw`{{< image-gallery-item href="7055cedc4c9ff2483d0adf2d4424e995_IMG_3446.jpg" data-ngdesc="Student blackboard drawing." text="For the top diagram, the viewer \[left vertical hash\] and the object \[right vertical hash\] stay fixed while the frame \[hash with arrow\] is moved to the right." >}}`,
  String.raw`{{< image-gallery-item href="b86a4dd13c56f6fc8e263fb2fa123363_lec2photo5.jpg" data-ngdesc="This map shows the actual outcrop distribution of Precambrian rocks." text="In the north here you can see a huge outcrop of older rocks, the Belt Group. They are 1.5 by to \<1 b.y. old." >}}`,
  String.raw`{{< image-gallery-item href="6a0fa6d53bd7c1b6773ea458f9acbe8d_IMG_0734.jpg" data-ngdesc="This Renaissance-era necklace uses Fimo clay, plastic beads, and metal washers. ({{% resource_link \"b74a514f-366d-4997-99ae-652baf717a15\" \"Inspiration\" %}})" text="This Renaissance-era necklace uses Fimo clay, plastic beads, and metal washers. ({{% resource_link \"b74a514f-366d-4997-99ae-652baf717a15\" \"Inspiration\" %}})" >}}`,
  '{{< image-gallery-item href="272d876d99c6f4a99e480cfbed32c6c6_horseshoe3.jpg" data-ngdesc="" text="Customers outside the Café — “the Horseshoe” in 1952…" >}}',
]

describe("ImageGallery plugin", () => {
  beforeEach(() => {
    handles = []
  })

  it("keeps realistic item text exactly, through a save and a reload", async () => {
    const markdown = [
      '{{< image-gallery id="b3c6b3e0-51d2-5533-55fb-a1fef08ed31a_nanogallery2" baseUrl="/courses/12-114-field-geology-i-fall-2005/" >}}',
      ...REAL_ITEMS,
      "{{< /image-gallery >}}",
    ].join("\n")
    const editor = await getEditor(markdown)

    expect(editor.getData()).toBe(markdown)
    expect(handles[0].getItems()).toEqual(
      REAL_ITEMS.map((item) =>
        item.slice("{{< image-gallery-item".length, -">}}".length),
      ),
    )
    editor.setData(editor.getData())
    expect(editor.getData()).toBe(markdown)
  })

  it("saves an item built from a complex caption, and loads it back unchanged", async () => {
    const editor = await getEditor("")
    const caption =
      'Niépce\'s "View from the Window."\r\n\r\nGypsum: CaSO{{< sub "4" >}}\\-2H{{< sub "2" >}}O, $5 ¨ 5\u00a0km'
    editor.execute("insertImageGallery", {
      params:
        ' baseUrl="/courses/12-108-structure-of-earth-materials-fall-2004/" ',
      items: [
        buildGalleryItem({
          ...makeWebsiteContentDetail(),
          text_id: "0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21",
          file: "https://ol-ocw-studio-app-production.s3.amazonaws.com/courses/12-108/328fb82d2a9b2a07c3f9dab9bb5a7367_lab4-4.jpg",
          metadata: { image_metadata: { caption } },
        }),
      ],
    })
    const saved = [
      '{{< image-gallery baseUrl="/courses/12-108-structure-of-earth-materials-fall-2004/" >}}',
      // With quotes in the text, its "\-" is written as "&#45;": Hugo drops
      // every backslash from a param containing \".
      String.raw`{{< image-gallery-item uuid="0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21" href="328fb82d2a9b2a07c3f9dab9bb5a7367_lab4-4.jpg" text="Niépce's \"View from the Window.\"  Gypsum: CaSO{{< sub 4 >}}&#45;2H{{< sub 2 >}}O, $5 ¨ 5${NBSP}km" >}}`,
      "{{< /image-gallery >}}",
    ].join("\n")

    expect(editor.getData()).toBe(saved)
    editor.setData(saved)
    expect(editor.getData()).toBe(saved)
  })

  it("keeps every param on the opening tag and on each item", async () => {
    const editor = await getEditor(PRODUCTION_GALLERY)
    expect(editor.getData()).toBe(
      [
        '{{< image-gallery id="788b6153-ce75-e1be-31f0-a394ce761f32_nanogallery2" baseUrl="/courses/18-05-introduction-to-probability-and-statistics-spring-2014/" >}}',
        String.raw`{{< image-gallery-item href="6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg" data-ngdesc="" text="The walls of our {{% resource_link \"c2956690-7ead-4f56-8282-fe998b987b00\" \"TEAL classroom\" %}} are lined with whiteboards." >}}`,
        '{{< image-gallery-item uuid="0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21" href="ffd3fea2cf932a2072579f1182251e33_staurolite.jpg" data-ngdesc="Staurolite" text="Staurolite: Fe{{< sub 2 >}}Al{{< sub 9 >}}Si{{< sub 4 >}}" >}}',
        "{{< /image-gallery >}}",
      ].join("\n"),
    )
  })

  it("keeps characters that showdown rewrites before extensions run", async () => {
    const markdown = [
      "{{< image-gallery >}}",
      '{{< image-gallery-item href="a.jpg" text="Costs $5, naïve ¨, 5\u00a0km" >}}',
      "{{< /image-gallery >}}",
    ].join("\n")
    const editor = await getEditor(markdown)
    expect(editor.getData()).toBe(markdown)
  })

  it("keeps two galleries and the prose around them separate", async () => {
    const markdown = [
      "Before.",
      "",
      '{{< image-gallery id="first" >}}',
      '{{< image-gallery-item href="a.jpg" >}}',
      "{{< /image-gallery >}}",
      "",
      "Between.",
      "",
      '{{< image-gallery baseUrl="/courses/x/" >}}',
      '{{< image-gallery-item href="b.jpg" >}}',
      "{{< /image-gallery >}}",
      "",
      "After.",
    ].join("\n")
    const editor = await getEditor(markdown)
    expect(editor.getData()).toBe(markdown)
  })

  it("gives the widget each item's raw params, and saves the order it sets", async () => {
    const editor = await getEditor(PRODUCTION_GALLERY)
    expect(handles).toHaveLength(1)
    const [handle] = handles
    expect(handle.getItems()).toEqual([
      String.raw` href="6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg" data-ngdesc="" text="The walls of our {{% resource_link \"c2956690-7ead-4f56-8282-fe998b987b00\" \"TEAL classroom\" %}} are lined with whiteboards." `,
      ' uuid="0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21" href="ffd3fea2cf932a2072579f1182251e33_staurolite.jpg" data-ngdesc="Staurolite" text="Staurolite: Fe{{< sub 2 >}}Al{{< sub 9 >}}Si{{< sub 4 >}}" ',
    ])

    handle.setItems([...handle.getItems()].reverse())

    expect(editor.getData()).toBe(
      [
        '{{< image-gallery id="788b6153-ce75-e1be-31f0-a394ce761f32_nanogallery2" baseUrl="/courses/18-05-introduction-to-probability-and-statistics-spring-2014/" >}}',
        '{{< image-gallery-item uuid="0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21" href="ffd3fea2cf932a2072579f1182251e33_staurolite.jpg" data-ngdesc="Staurolite" text="Staurolite: Fe{{< sub 2 >}}Al{{< sub 9 >}}Si{{< sub 4 >}}" >}}',
        String.raw`{{< image-gallery-item href="6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg" data-ngdesc="" text="The walls of our {{% resource_link \"c2956690-7ead-4f56-8282-fe998b987b00\" \"TEAL classroom\" %}} are lined with whiteboards." >}}`,
        "{{< /image-gallery >}}",
      ].join("\n"),
    )
  })

  it("keeps key presses inside the gallery's controls away from CKEditor", async () => {
    const editor = await getEditor(PRODUCTION_GALLERY)
    const root = editor.editing.view.getDomRoot()!
    const wrapper = root.querySelector(".image-gallery-react-wrapper")!
    // Stand-in for one of the widget's buttons, which React renders here.
    const button = wrapper.appendChild(document.createElement("button"))
    const keydown = jest.fn()
    editor.editing.view.document.on("keydown", keydown)

    button.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    )
    expect(keydown).not.toHaveBeenCalled()

    // The same key press from ordinary content does reach CKEditor.
    root.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    )
    expect(keydown).toHaveBeenCalledTimes(1)
  })

  it("still undoes and redoes from the keyboard inside the gallery's controls", async () => {
    const editor = await getEditorWithUndo(PRODUCTION_GALLERY)
    const original = handles[0].getItems()
    const reversed = [...original].reverse()
    handles[0].setItems(reversed)
    const button = editor.editing.view
      .getDomRoot()!
      .querySelector(".image-gallery-react-wrapper")!
      .appendChild(document.createElement("button"))
    const press = (init: KeyboardEventInit) =>
      button.dispatchEvent(
        new KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          ...init,
        }),
      )

    press({ key: "z", keyCode: 90, ctrlKey: true })
    expect(handles[0].getItems()).toEqual(original)
    press({ key: "y", keyCode: 89, ctrlKey: true })
    expect(handles[0].getItems()).toEqual(reversed)
    press({ key: "z", keyCode: 90, ctrlKey: true })
    press({ key: "Z", keyCode: 90, ctrlKey: true, shiftKey: true })
    expect(handles[0].getItems()).toEqual(reversed)
  })

  it("asks the host to pick images, for a gallery or for a new one", async () => {
    const openImageGalleryPicker = jest.fn()
    const editor = await getEditor(PRODUCTION_GALLERY, {
      [CKEDITOR_RESOURCE_UTILS]: {
        ...resourceUtils[CKEDITOR_RESOURCE_UTILS],
        openImageGalleryPicker,
      },
    })

    handles[0].openPicker()
    expect(openImageGalleryPicker).toHaveBeenLastCalledWith(handles[0])

    // The toolbar button: the picker's choice becomes a new gallery.
    editor.ui.componentFactory.create(ADD_IMAGE_GALLERY).fire("execute")
    expect(openImageGalleryPicker).toHaveBeenLastCalledWith(null)
  })

  it("drops a gallery once its last item is removed", async () => {
    const editor = await getEditor(
      [
        "Before.",
        "",
        "{{< image-gallery >}}",
        '{{< image-gallery-item href="a.jpg" >}}',
        "{{< /image-gallery >}}",
        "",
        "After.",
      ].join("\n"),
    )
    handles[0].setItems([])
    expect(editor.getData()).toBe("Before.\n\nAfter.")
  })

  it("inserts a new gallery with the opening params and items it is given", async () => {
    const editor = await getEditor("")
    editor.execute("insertImageGallery", {
      params: ' baseUrl="/courses/x/" ',
      items: [' uuid="u1" href="a.jpg" text="Cap" '],
    })
    expect(editor.getData()).toBe(
      [
        '{{< image-gallery baseUrl="/courses/x/" >}}',
        '{{< image-gallery-item uuid="u1" href="a.jpg" text="Cap" >}}',
        "{{< /image-gallery >}}",
      ].join("\n"),
    )
  })
})
