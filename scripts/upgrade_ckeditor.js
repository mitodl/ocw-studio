const fs = require("fs")
const child_process = require("child_process")
const { Command } = require("commander")

const ckeditorRegex = /@ckeditor\/.*/

const packageJson = JSON.parse(fs.readFileSync("./package.json"))
const ckeditorDependencies = Object.keys(packageJson.dependencies)
  .filter(dependency => ckeditorRegex.test(dependency))
  .join(" ")

const program = new Command()

program
  .name("upgrade_ckeditor.js")
  .option("--upgrade", "upgrade to latest version (runs `yarn add`)")

program.parse(process.argv)

const options = program.opts()

// this is just a little wrapper to cut down on the warning spew from yarn
const promiseExec = command => {
  return new Promise((resolve, reject) => {
    child_process.exec(command, (error, _, stderr) => {
      if (error) {
        reject(stderr)
      } else {
        resolve()
      }
    })
  })
}

async function main() {
  if (options.upgrade) {
    console.log("running full upgrade of all @ckeditor/ packages to @latest...")
    try {
      await promiseExec(`yarn --ignore-engines add ${ckeditorDependencies}`)
      console.log("upgrade done!")
    } catch (e) {
      console.error(e)
    }
  } else {
    console.log("running update of all @ckeditor/ packages...")
    try {
      await promiseExec(`yarn --ignore-engines upgrade ${ckeditorDependencies}`)
      console.log("update done!")
    } catch (e) {
      console.error(e)
    }
  }
}

main()
