import UrlAssembler from "url-assembler"

const alphabeticalSort = (a: string, b: string) => a.localeCompare(b)

// This is our re-exported instance of UrlAssembler
// which has a configuration object passed in for use by
// the query-string module.
//
// The `sort` function passed in here is called by qs.stringify
// before it renders the query parameters out to a string, which
// means that passing query parameters in any order to a URL built
// with UrlAssembler will return the same overall URL, instead of
// being order dependent.
const OurUrlAssembler = UrlAssembler().qsConfig({
  sort: alphabeticalSort,
})

export default OurUrlAssembler
