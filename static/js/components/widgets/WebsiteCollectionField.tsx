import React, { useCallback, useEffect, useState } from "react"

import SortableSelect, { SortableItem } from "./SortableSelect"
import { Option } from "./SelectField"
import { useWebsiteSelectOptions, WebsiteOption } from "../../hooks/websites"
import _ from "lodash"

interface Props {
  name: string
  onChange: (event: any) => void
  value: SortableItem[]
}

export function formatOptionsLabelWithShortId(
  options: WebsiteOption[]
): WebsiteOption[] {
  const formattedOptions = _.cloneDeep(options)
  formattedOptions.forEach(e => {
    e.label = `${e.label} (${e.shortId})`
  })
  return formattedOptions
}

export default function WebsiteCollectionField(props: Props): JSX.Element {
  const { name, onChange, value } = props

  const [websiteMap, setWebsiteMap] = useState<Map<string, string>>(
    new Map(value.map(item => [item.id, item.title]))
  )

  /**
   * A little shim where we make a fake event 🤫
   */
  const onChangeShim = useCallback(
    (value: string[]) => {
      const updatedEvent = {
        target: {
          name:  name.replace(/\.content$/, ""),
          value: value.map(id => ({
            id,
            title: websiteMap.get(id) ?? id
          }))
        }
      }
      onChange(updatedEvent)
    },
    [onChange, websiteMap, name]
  )

  const { options, loadOptions } = useWebsiteSelectOptions("url_path", true)

  useEffect(() => {
    setWebsiteMap(cur => {
      const newMap = new Map(cur)
      options.forEach(({ value, label }) => {
        newMap.set(value, label)
      })
      return newMap
    })
  }, [options, setWebsiteMap])

  const isOptionDisabled = useCallback(
    (option: Option) => {
      return value.some(v => v.id === option.value)
    },
    [value]
  )

  const formattedOptions = formatOptionsLabelWithShortId(options)

  return (
    <SortableSelect
      name={name}
      value={value}
      onChange={onChangeShim}
      options={formattedOptions}
      defaultOptions={formattedOptions}
      loadOptions={loadOptions}
      isOptionDisabled={isOptionDisabled}
    />
  )
}
