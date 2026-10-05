import {
  buildGalleryItem,
  galleryBaseUrl,
  parseGalleryItem,
} from "./galleryItems"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail,
} from "../../../util/factories/websites"
import { WebsiteContent } from "../../../types/websites"

const imageResource = (
  file: string | undefined,
  caption?: string,
): WebsiteContent => ({
  ...makeWebsiteContentDetail(),
  text_id: "c2956690-7ead-4f56-8282-fe998b987b00",
  file,
  metadata: {
    resourcetype: "Image",
    image_metadata: {
      "image-alt": "A classroom",
      ...(caption === undefined ? {} : { caption }),
      credit: "",
    },
  },
})

describe("parseGalleryItem", () => {
  it("reads uuid, href and text from an item's raw params", () => {
    expect(
      parseGalleryItem(
        ' uuid="c2956690-7ead-4f56-8282-fe998b987b00" href="6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg" data-ngdesc="" text="The walls" ',
      ),
    ).toEqual({
      uuid: "c2956690-7ead-4f56-8282-fe998b987b00",
      href: "6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg",
      text: "The walls",
    })
  })

  it("unescapes quotes inside a value", () => {
    expect(
      parseGalleryItem(
        String.raw` href="a.jpg" text="{{% resource_link \"u1\" \"Spindle\" %}} - The screw" `,
      ).text,
    ).toBe('{{% resource_link "u1" "Spindle" %}} - The screw')
  })

  it("leaves uuid undefined for a legacy item that only has an href", () => {
    expect(
      parseGalleryItem(' href="f67182bb6685b36e6068ba1c52e1e9fe_13.jpg" '),
    ).toEqual({
      uuid: undefined,
      href: "f67182bb6685b36e6068ba1c52e1e9fe_13.jpg",
      text: undefined,
    })
  })

  it("returns nothing, rather than throwing, for params that do not parse", () => {
    expect(parseGalleryItem(' href="unterminated.jpg text="x" ')).toEqual({})
  })
})

describe("buildGalleryItem", () => {
  it("writes uuid, the file's basename as href, and the caption as text", () => {
    expect(
      buildGalleryItem(
        imageResource(
          "https://ol-ocw-studio-app-production.s3.amazonaws.com/courses/18-05/6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg",
          "The walls of our classroom",
        ),
      ),
    ).toBe(
      ' uuid="c2956690-7ead-4f56-8282-fe998b987b00" href="6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg" text="The walls of our classroom" ',
    )
  })

  it("URL-decodes the filename", () => {
    expect(
      parseGalleryItem(
        buildGalleryItem(
          imageResource(
            "http://localhost:9000/ol-ocw-studio-app-local/courses/finding-nemo/blue%20tang.jpg",
            "",
          ),
        ),
      ).href,
    ).toBe("blue tang.jpg")
  })

  it("escapes quotes and flattens newlines in the caption", () => {
    expect(
      buildGalleryItem(imageResource("/a/b.jpg", 'He said "hi"\nthen left')),
    ).toBe(
      String.raw` uuid="c2956690-7ead-4f56-8282-fe998b987b00" href="b.jpg" text="He said \"hi\" then left" `,
    )
  })

  it("still writes an empty text when the image has no caption", () => {
    expect(buildGalleryItem(imageResource("/a/b.jpg"))).toBe(
      ' uuid="c2956690-7ead-4f56-8282-fe998b987b00" href="b.jpg" text="" ',
    )
  })

  it("leaves out href when the resource has no file", () => {
    expect(buildGalleryItem(imageResource(undefined, "Cap"))).toBe(
      ' uuid="c2956690-7ead-4f56-8282-fe998b987b00" text="Cap" ',
    )
  })
})

describe("buildGalleryItem with captions like the ones in production", () => {
  const captioned = (caption: string): WebsiteContent => ({
    ...imageResource(
      "https://ol-ocw-studio-app-production.s3.amazonaws.com/courses/18-05/6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg",
      caption,
    ),
    text_id: "0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21",
  })

  /**
   * `text` is the caption as course-v2 needs it on one line: each line break
   * becomes a space, so a paragraph break becomes two, and double quotes are
   * escaped. Production items written from these captions match that.
   * `readBack` is the value a shortcode parser takes out of the param again.
   */
  it.each([
    {
      label: "a multi-paragraph caption saved with Windows line endings",
      caption:
        'We had the students work on the whiteboards in groups of three.\r\n\r\nThe walls of our {{% resource_link "c2956690-7ead-4f56-8282-fe998b987b00" "Technology-Enabled Active Learning classroom" %}} are lined with whiteboards.',
      text: String.raw`We had the students work on the whiteboards in groups of three.  The walls of our {{% resource_link \"c2956690-7ead-4f56-8282-fe998b987b00\" \"Technology-Enabled Active Learning classroom\" %}} are lined with whiteboards.`,
      readBack:
        'We had the students work on the whiteboards in groups of three.  The walls of our {{% resource_link "c2956690-7ead-4f56-8282-fe998b987b00" "Technology-Enabled Active Learning classroom" %}} are lined with whiteboards.',
    },
    {
      label: "a glossary of links with a bare term between them",
      caption:
        '{{% resource_link "d625c74d-9975-490c-809c-f5593c583cce" "Spindle" %}} - The screw to which the bar of the press is affixed.\n\nNut\n\n{{% resource_link "7abde5b4-ba8e-4c3b-a5d3-32e0b0cebfc2" "Tympan" %}} - A frame covered with parchment.',
      text: String.raw`{{% resource_link \"d625c74d-9975-490c-809c-f5593c583cce\" \"Spindle\" %}} - The screw to which the bar of the press is affixed.  Nut  {{% resource_link \"7abde5b4-ba8e-4c3b-a5d3-32e0b0cebfc2\" \"Tympan\" %}} - A frame covered with parchment.`,
      readBack:
        '{{% resource_link "d625c74d-9975-490c-809c-f5593c583cce" "Spindle" %}} - The screw to which the bar of the press is affixed.  Nut  {{% resource_link "7abde5b4-ba8e-4c3b-a5d3-32e0b0cebfc2" "Tympan" %}} - A frame covered with parchment.',
    },
    {
      label: "a credit folded into the caption, with straight quotes",
      caption:
        'Niépce\'s "View from the Window at Le Gras." Image is in the public domain. Source: {{% resource_link "6c5b1c0c-e574-4034-b729-c413c0f398f5" "Wikimedia Commons" %}}.',
      text: String.raw`Niépce's \"View from the Window at Le Gras.\" Image is in the public domain. Source: {{% resource_link \"6c5b1c0c-e574-4034-b729-c413c0f398f5\" \"Wikimedia Commons\" %}}.`,
      readBack:
        'Niépce\'s "View from the Window at Le Gras." Image is in the public domain. Source: {{% resource_link "6c5b1c0c-e574-4034-b729-c413c0f398f5" "Wikimedia Commons" %}}.',
    },
    {
      // Hugo drops every backslash from a param that contains \" so, written
      // quoted, the escaped hyphen would reach course-v2 as a bare "-".
      // Production items write simple sub values unquoted, which needs no \".
      label:
        "a formula, with simple sub values unquoted as production writes them",
      caption: String.raw`Gypsum twins: CaSO{{< sub "4" >}}\-2H{{< sub "2" >}}O.`,
      text: String.raw`Gypsum twins: CaSO{{< sub 4 >}}\-2H{{< sub 2 >}}O.`,
      readBack: String.raw`Gypsum twins: CaSO{{< sub 4 >}}\-2H{{< sub 2 >}}O.`,
    },
    {
      label: "a sup value with spaces, which stays quoted",
      caption: 'Term x{{< sup "n + 1" >}}',
      text: String.raw`Term x{{< sup \"n + 1\" >}}`,
      readBack: 'Term x{{< sup "n + 1" >}}',
    },
    {
      label:
        "typography and other Markdown escapes, which pass through as they are",
      caption: String.raw`Rocks 5 µm across at 20 °C — ® “quoted” \[signed:\] CaF₂, \<1 b.y. \*not\* bold…`,
      text: String.raw`Rocks 5 µm across at 20 °C — ® “quoted” \[signed:\] CaF₂, \<1 b.y. \*not\* bold…`,
      readBack: String.raw`Rocks 5 µm across at 20 °C — ® “quoted” \[signed:\] CaF₂, \<1 b.y. \*not\* bold…`,
    },
    {
      // The quotes are written as \" and Hugo then drops every backslash from
      // the param, so each escape is written as the character it stands for.
      label:
        "straight quotes with Markdown escapes, written as character references",
      caption: String.raw`He said "x": \*literal\* \[y\] \_z\_ \<1`,
      text: String.raw`He said \"x\": &#42;literal&#42; &#91;y&#93; &#95;z&#95; &#60;1`,
      readBack: 'He said "x": &#42;literal&#42; &#91;y&#93; &#95;z&#95; &#60;1',
    },
    {
      label:
        "a link with an escape in its title next to an escape in the prose",
      caption: String.raw`See {{% resource_link "c2956690-7ead-4f56-8282-fe998b987b00" "Fig. \[1\]" %}}: \*not\* bold`,
      text: String.raw`See {{% resource_link \"c2956690-7ead-4f56-8282-fe998b987b00\" \"Fig. &#91;1&#93;\" %}}: &#42;not&#42; bold`,
      readBack:
        'See {{% resource_link "c2956690-7ead-4f56-8282-fe998b987b00" "Fig. &#91;1&#93;" %}}: &#42;not&#42; bold',
    },
    {
      // Hugo fails the whole page build on "\`" inside a quoted shortcode
      // param ("unrecognized escape character"). Production items write the
      // backtick as &grave; instead, which renders the same.
      label: "an escaped backtick, written as &grave; as production items do",
      caption: String.raw`Dar al-\`Adl as represented by Robert Hay in his Illustrations of Cairo (1840).`,
      text: "Dar al-&grave;Adl as represented by Robert Hay in his Illustrations of Cairo (1840).",
      readBack:
        "Dar al-&grave;Adl as represented by Robert Hay in his Illustrations of Cairo (1840).",
    },
  ])("$label", ({ caption, text, readBack }) => {
    const item = buildGalleryItem(captioned(caption))
    expect(item).toBe(
      ` uuid="0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21" href="6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg" text="${text}" `,
    )
    expect(parseGalleryItem(item).text).toBe(readBack)
  })
})

describe("galleryBaseUrl", () => {
  it("uses the site's URL path", () => {
    expect(
      galleryBaseUrl(
        makeWebsiteDetail({
          url_path:
            "courses/18-05-introduction-to-probability-and-statistics-spring-2014",
        }),
      ),
    ).toBe(
      "/courses/18-05-introduction-to-probability-and-statistics-spring-2014/",
    )
  })

  it("falls back to the URL suggestion under the starter's root path", () => {
    expect(
      galleryBaseUrl(
        makeWebsiteDetail({
          url_path: null,
          url_suggestion: "18-05-introduction-to-probability-spring-2014",
        }),
      ),
    ).toBe("/courses/18-05-introduction-to-probability-spring-2014/")
  })

  it("gives up when the suggestion still has unfilled metadata sections", () => {
    expect(
      galleryBaseUrl(
        makeWebsiteDetail({
          url_path: null,
          url_suggestion: "18-05-[sitemetadata:term]-2014",
        }),
      ),
    ).toBeNull()
  })
})
