import React, { useMemo } from "react"
import { ErrorMessage, Field, Form, Formik, FormikHelpers } from "formik"
import * as yup from "yup"

import { InternalSortableMenuItem } from "../widgets/MenuField"
import RelationField from "../widgets/RelationField"
import { FormError } from "./FormError"

import { LinkType, WebsiteContent } from "../../types/websites"

interface Props {
  onSubmit: (
    values: any,
    formikHelpers: FormikHelpers<any>
  ) => void | Promise<any>
  activeItem: InternalSortableMenuItem | null
  collections?: string[]
  existingMenuIds?: Set<string>
  contentContext: WebsiteContent[] | null
}

export type MenuItemFormValues = {
  menuItemTitle: string
  menuItemType: LinkType.Internal | LinkType.External
  externalLink: string
  internalLink: string
}

const schema = yup.object().shape({
  menuItemTitle: yup.string().required().label("Title"),
  menuItemType:  yup.mixed().oneOf([LinkType.Internal, LinkType.External]),
  externalLink:  yup.string().label("External link").url().when("menuItemType", {
    is:   LinkType.External,
    then: yup.string().required()
  }),
  internalLink: yup.string().label("Internal link").when("menuItemType", {
    is:   LinkType.Internal,
    then: yup.string().required()
  })
})

const emptyInitialValues: MenuItemFormValues = {
  menuItemTitle: "",
  menuItemType:  LinkType.Internal,
  externalLink:  "",
  internalLink:  ""
}

export default function MenuItemForm({
  onSubmit,
  activeItem,
  collections,
  existingMenuIds,
  contentContext
}: Props): JSX.Element {
  const initialValues = useMemo(
    () =>
      activeItem ?
        {
          menuItemTitle: activeItem.text,
          menuItemType:  activeItem.targetUrl ?
            LinkType.External :
            LinkType.Internal,
          externalLink: activeItem.targetUrl || "",
          internalLink: activeItem.targetContentId || ""
        } :
        emptyInitialValues,
    [activeItem]
  )

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={schema}
      initialValues={initialValues}
      enableReinitialize={true}
    >
      {({ isSubmitting, status, setFieldValue, values }) => {
        return (
          <Form className="row">
            <div className="form-group w-100">
              <label className="px-2" htmlFor="menuItemTitle">
                Title
              </label>
              <Field
                id="menuItemTitle"
                name="menuItemTitle"
                className="form-control"
              />
              <ErrorMessage name="menuItemTitle" component={FormError} />
            </div>
            <div className="form-group w-100">
              <input
                type="radio"
                id="menuItemTypeInternal"
                name="menuItemType"
                value={LinkType.Internal}
                checked={values.menuItemType === LinkType.Internal}
                onChange={() => {
                  setFieldValue("menuItemType", LinkType.Internal)
                }}
              />
              <label className="px-2" htmlFor="menuItemTypeInternal">
                Internal
              </label>
              <input
                type="radio"
                id="menuItemTypeExternal"
                name="menuItemType"
                value={LinkType.External}
                checked={values.menuItemType === LinkType.External}
                onChange={() => {
                  setFieldValue("menuItemType", LinkType.External)
                }}
              />
              <label className="px-2" htmlFor="menuItemTypeExternal">
                External
              </label>
            </div>
            <div className="form-group w-100">
              {values.menuItemType === LinkType.Internal ? (
                <>
                  <label className="px-2" htmlFor="internalLink">
                    Link to:
                  </label>
                  <RelationField
                    name="internalLink"
                    collection={collections}
                    display_field="title"
                    multiple={false}
                    onChange={event => {
                      setFieldValue("internalLink", event.target.value.content)
                    }}
                    value={values.internalLink}
                    valuesToOmit={existingMenuIds}
                    contentContext={contentContext}
                  />
                  <ErrorMessage name="internalLink" component={FormError} />
                </>
              ) : (
                <>
                  <label className="px-2" htmlFor="externalLink">
                    Link to:
                  </label>
                  <Field
                    id="externalLink"
                    name="externalLink"
                    className="form-control"
                  />
                  <span className="help-text">
                    URL, e.g. http://example.com
                  </span>
                  <ErrorMessage name="externalLink" component={FormError} />
                </>
              )}
            </div>
            <div className="form-group d-flex w-100 justify-content-end">
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-5 btn cyan-button"
              >
                Save
              </button>
            </div>
            {status && (
              // Status is being used to store non-field errors
              <div className="form-error">{status}</div>
            )}
          </Form>
        )
      }}
    </Formik>
  )
}
