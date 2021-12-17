import { ReactWrapper } from "enzyme"
import { act } from "react-dom/test-utils"

/**
 * A little helper function to find the SelectField
 * inside of another component and call its onChange
 * handler with a specific value.
 *
 * Just to DRY up some boilerplate!
 */
export async function triggerSortableSelect(wrapper: ReactWrapper, value: any) {
  await act(async () => {
    // @ts-ignore
    wrapper.find("SelectField").prop("onChange")({
      // @ts-ignore
      target: { value }
    })
  })
  wrapper.update()
  wrapper.find(".cyan-button").simulate("click")
}
