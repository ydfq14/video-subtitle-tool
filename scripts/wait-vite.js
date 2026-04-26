const http = require('http')

const maxRetries = 30
const retryDelay = 1000
let retries = 0

function checkVite() {
  const req = http.get('http://localhost:5173', (res) => {
    if (res.statusCode === 200) {
      console.log('Vite server is ready!')
      process.exit(0)
    }
  })

  req.on('error', () => {
    retries++
    if (retries < maxRetries) {
      console.log(`Waiting for Vite server... (${retries}/${maxRetries})`)
      setTimeout(checkVite, retryDelay)
    } else {
      console.error('Vite server did not start in time')
      process.exit(1)
    }
  })

  req.end()
}

checkVite()
