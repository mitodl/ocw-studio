export default function* incrementer(): Generator<number, number, number> {
  let int = 1
  // eslint-disable-next-line no-constant-condition
  while (true) {
    yield int++
  }
}
