import React, { useMemo } from "react"
import { ErrorMessage, Field, Form, Formik, FormikHelpers } from "formik"
import * as yup from "yup"

import { SortableMenuItem } from "../widgets/MenuField"
import RelationField from "../widgets/RelationField"
import { FormError } from "./FormError"

import { WebsiteContent } from "../../types/websites"

interface Props {
  onSubmit: (
    values: any,
    formikHelpers: FormikHelpers<any>,
  ) => void | Promise<any>
  activeItem: SortableMenuItem | null
  collections?: string[]
  existingMenuIds?: Set<string>
  contentContext: WebsiteContent[] | null
}

export type MenuItemFormValues = {
  menuItemTitle: string
  contentLink: string
}

const schema = yup.object().shape({
  menuItemTitle: yup.string().required().label("Title"),
  contentLink: yup.string().required().label("Link"),
})

const emptyInitialValues: MenuItemFormValues = {
  menuItemTitle: "",
  contentLink: "",
}

export default function MenuItemForm({
  onSubmit,
  activeItem,
  collections,
  existingMenuIds,
  contentContext,
}: Props): JSX.Element {
  const initialValues = useMemo(
    () =>
      activeItem
        ? {
            menuItemTitle: activeItem.text,
            contentLink: activeItem.targetContentId || "",
          }
        : emptyInitialValues,
    [activeItem],
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
              <label className="px-2" htmlFor="contentLink">
                Link to:
              </label>
              <RelationField
                name="contentLink"
                collection={collections}
                display_field="title"
                multiple={false}
                onChange={(event) => {
                  setFieldValue("contentLink", event.target.value.content)
                }}
                value={values.contentLink}
                valuesToOmit={existingMenuIds}
                contentContext={contentContext}
              />
              <ErrorMessage name="contentLink" component={FormError} />
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
