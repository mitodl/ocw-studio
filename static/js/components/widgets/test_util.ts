import { ReactWrapper } from "enzyme"
import { act } from "react-dom/test-utils"
import { assertNotNil } from "../../test_util"
import { isFeatureEnabled } from "../../util/features"

/**
 * A little helper function to find the SelectField
 * inside of another component and call its onChange
 * handler with a specific value.
 *
 * Just to DRY up some boilerplate!
 */
export async function triggerSortableSelect(wrapper: ReactWrapper, value: any) {
  await act(async () => {
    const onChange = wrapper.find("SelectField").prop("onChange")
    assertNotNil(onChange)
    onChange({
      // @ts-expect-error Not simnulating the whole event
      target: { value }
    })
  })

  if (!isFeatureEnabled("SORTABLE_SELECT_QUICK_ADD")) {
    wrapper.find(".cyan-button").simulate("click")
  }
}

/**
 * A utility to help trigger (open/close) the menu
 * of the Select component.
 */
export async function triggerSelectMenu(
  wrapper: ReactWrapper,
  prefix = "select"
) {
  await act(async () => {
    wrapper
      .find(`.${prefix}__dropdown-indicator`)
      .hostNodes()
      .simulate("mouseDown", {
        button: 0
      })
  })
  wrapper.update()
}
