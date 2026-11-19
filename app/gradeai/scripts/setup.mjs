// One-time setup on this computer: creates .env with a private worker token and your Fir username.
//   npm run setup                (asks for your Alliance username)
//   npm run setup -- rudyniki
import crypto from 'node:crypto'
import fs from 'node:fs'
import readline from 'node:readline/promises'

const envFile = new URL('../.env', import.meta.url)
const example = new URL('../.env.example', import.meta.url)
const existed = fs.existsSync(envFile)
let text = fs.readFileSync(existed ? envFile : example, 'utf8')

const get = key => (text.match(new RegExp(`^${key}=(.*)$`, 'm'))?.[1] ?? '').trim()
const set = (key, value) => {
  const line = new RegExp(`^#?\\s*${key}=.*$`, 'm')
  text = line.test(text) ? text.replace(line, `${key}=${value}`) : `${text.trimEnd()}\n${key}=${value}\n`
}

if (!get('WORKER_TOKEN')) set('WORKER_TOKEN', crypto.randomBytes(32).toString('hex'))

let user = process.argv[2] || get('FIR_USER')
while (!/^[a-z][a-z0-9_-]*$/i.test(user)) {
  if (!process.stdin.isTTY) { console.error('Pass your Alliance username: npm run setup -- <username>'); process.exit(1) }
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout })
  user = (await rl.question('Your Alliance username (the one you use to ssh to Fir): ')).trim()
  rl.close()
}
set('FIR_USER', user)

fs.writeFileSync(envFile, text, { mode: 0o600 })
fs.chmodSync(envFile, 0o600)
console.log(`${existed ? 'Updated' : 'Created'} .env (Fir user ${user}).`)
console.log(`
Next:
  npm run build            # once, and after updating GradeAI
  npm start                # GradeAI at http://localhost:${get('PORT') || 8080}
  npm run model:connect    # in a second terminal: start the model on Fir and connect it
`)
