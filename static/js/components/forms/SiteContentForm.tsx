import React, { useEffect, useMemo } from "react"
import {
  Field,
  Form,
  Formik,
  FormikHelpers,
  FormikValues,
  FormikProps,
  validateYupSchema,
  yupToFormErrors,
  FormikErrors,
} from "formik"

import SiteContentField from "./SiteContentField"
import ObjectField from "../widgets/ObjectField"
import Label from "../widgets/Label"

import {
  contentInitialValues,
  fieldIsVisible,
  newInitialValues,
  renameNestedFields,
} from "../../lib/site_content"
import { scrollToElement } from "../../util/dom"

import {
  ConfigField,
  EditableConfigItem,
  WebsiteContent,
  WebsiteContentModalState,
  WidgetVariant,
} from "../../types/websites"
import { SiteFormValues } from "../../types/forms"
import { getContentSchema } from "./validation"
import { useWebsite } from "../../context/Website"
import { filenameFromPath } from "../../lib/util"

export interface FormProps {
  onSubmit: (
    values: any,
    formikHelpers: FormikHelpers<any>,
  ) => void | Promise<any>
  configItem: EditableConfigItem
  content: WebsiteContent | null
  editorState: WebsiteContentModalState
  setDirty: (dirty: boolean) => void
}

export default function SiteContentForm(props: FormProps): JSX.Element {
  const { onSubmit, configItem, content, editorState } = props
  const website = useWebsite()
  const initialValues: SiteFormValues = useMemo(
    () =>
      editorState.adding()
        ? {
            ...newInitialValues(configItem.fields, website),
            ...(configItem.name === "resource"
              ? { resourcetype: "Video" }
              : {}),
          }
        : contentInitialValues(
            content as WebsiteContent,
            configItem.fields,
            website,
          ),
    [configItem.fields, configItem.name, editorState, content, website],
  )

  const validate = async (
    values: FormikValues,
  ): Promise<FormikErrors<SiteFormValues>> => {
    const schema = getContentSchema(configItem, values)

    try {
      await validateYupSchema(values, schema)
    } catch (e) {
      return yupToFormErrors(e)
    }
    return {}
  }

  // Auto-populate thumbnail for Video Resource on Save
  const handleSubmit = async (
    values: FormikValues,
    formikHelpers: FormikHelpers<any>,
  ) => {
    if (values.resourcetype === "Video") {
      const youtubeId = values?.video_metadata?.youtube_id
      if (youtubeId) {
        if (!values.video_files) {
          values.video_files = {}
        }
        if (!values.video_files.video_thumbnail_file) {
          values.video_files.video_thumbnail_file = `https://img.youtube.com/vi/${youtubeId}/default.jpg`
        }
        if (!values.video_metadata.source) {
          values.video_metadata.source = "youtube"
        }
      }
    }
    return onSubmit(values, formikHelpers)
  }

  return (
    <Formik
      onSubmit={handleSubmit}
      validate={validate}
      initialValues={initialValues}
      enableReinitialize={true}
    >
      {(formikProps) => (
        <FormFields validate={validate} {...formikProps} {...props} />
      )}
    </Formik>
  )
}

export interface InnerFormProps extends FormikProps<SiteFormValues>, FormProps {
  validate: (values: FormikValues) => Promise<FormikErrors<SiteFormValues>>
}

export function FormFields(props: InnerFormProps): JSX.Element {
  const {
    isSubmitting,
    status,
    values,
    handleChange,
    dirty,
    configItem,
    content,
    setDirty,
    handleSubmit,
    validate,
    editorState,
  } = props

  const contentContext = content?.content_context ?? null
  const renamedFields: ConfigField[] = useMemo(
    () => renameNestedFields(configItem.fields),
    [configItem],
  )

  useEffect(() => {
    setDirty(dirty)
  }, [setDirty, dirty])

  return (
    <Form
      onSubmit={async (event) => {
        handleSubmit(event)
        const { target } = event // get target before the await; https://reactjs.org/docs/legacy-event-pooling.html
        const errors = await validate(values)
        if (Object.keys(errors).length > 0) {
          scrollToElement(target as HTMLElement, ".form-error")
        }
      }}
    >
      <div>
        {renamedFields
          .filter((field) => fieldIsVisible(field, values))
          .map((field) => {
            // Hide `resourcetype` and `file` in case of adding Video Resource (using YouTube ID)
            if (
              configItem.name === "resource" &&
              (field.name === "resourcetype" || field.name === "file") &&
              editorState.adding()
            ) {
              return null
            }
            if (field.name === "title") {
              return (
                <React.Fragment key={field.name}>
                  <SiteContentField
                    field={field}
                    contentContext={contentContext}
                    onChange={handleChange}
                  />
                  {content?.type === "page" ? (
                    <div>
                      <label htmlFor="page-url">Page URL</label>
                      <div className="help-text">
                        This is auto-generated from the title field
                      </div>
                      <Label
                        value={`/pages/${content.filename}`}
                        name="page-url"
                      />
                    </div>
                  ) : null}
                </React.Fragment>
              )
            }
            return field.widget === WidgetVariant.Object ? (
              <ObjectField
                field={field}
                key={field.name}
                contentContext={contentContext}
                values={values}
                onChange={handleChange}
              />
            ) : SETTINGS.gdrive_enabled &&
              content?.type === "resource" &&
              field.widget === WidgetVariant.File ? (
              <div key={field.name}>
                <label htmlFor={field.name}>{field.label}</label>
                <Field
                  as={Label}
                  name={field.name}
                  value={filenameFromPath(values[field.name] as string)}
                  className="form-control"
                  onChange={handleChange}
                />
              </div>
            ) : (
              <SiteContentField
                field={field}
                key={field.name}
                contentContext={contentContext}
                onChange={handleChange}
              />
            )
          })}
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
}
