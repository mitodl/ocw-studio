import casual from "casual"
import { uniqueId } from "lodash"

export const uniqueWord = () => uniqueId(casual.word)
