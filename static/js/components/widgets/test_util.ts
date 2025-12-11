import { within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { isFeatureEnabled } from "../../util/features"

/**
 * A little helper function to find the SelectField
 * inside of another component and call its onChange
 * handler with a specific value.
 *
 * Just to DRY up some boilerplate!
 */
export async function triggerSortableSelect(
  container: HTMLElement,
  value: any,
) {
  const user = userEvent.setup()
  const selectInput = container.querySelector(
    ".form-input input[id^='react-select']",
  ) as HTMLElement

  await user.click(selectInput)

  const menu = document.querySelector("[class*='-menu']")
  if (menu) {
    const option = within(menu as HTMLElement).getByText(value)
    await user.click(option)
  }

  if (!isFeatureEnabled("SORTABLE_SELECT_QUICK_ADD")) {
    const addButton = container.querySelector(".cyan-button") as HTMLElement
    if (addButton) {
      await user.click(addButton)
    }
  }
}

/**
 * A utility to help trigger (open/close) the menu
 * of the Select component.
 */
export async function triggerSelectMenu(
  container: HTMLElement,
  prefix = "select",
) {
  const user = userEvent.setup()
  const dropdownIndicator = container.querySelector(
    `.${prefix}__dropdown-indicator`,
  ) as HTMLElement

  if (dropdownIndicator) {
    await user.click(dropdownIndicator)
  }
}
