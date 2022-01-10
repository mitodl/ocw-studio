import React, { useCallback, useEffect, useState } from "react"

import SortableSelect, { SortableItem } from "./SortableSelect"
import { useWebsiteSelectOptions } from "../../hooks/websites"

interface Props {
  name: string
  onChange: (event: any) => void
  value: SortableItem[]
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

  const { options, loadOptions } = useWebsiteSelectOptions("name")

  useEffect(() => {
    setWebsiteMap(cur => {
      const newMap = new Map(cur)
      options.forEach(({ value, label }) => {
        newMap.set(value, label)
      })
      return newMap
    })
  }, [options, setWebsiteMap])

  return (
    <SortableSelect
      name={name}
      value={value}
      onChange={onChangeShim}
      options={options}
      defaultOptions={options}
      loadOptions={loadOptions}
    />
  )
}
