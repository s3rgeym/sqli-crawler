const choice = arr => arr[(Math.random() * arr.length) | 0]

function fillFields(form) {
  for (let field of form.elements) {
    if (field.value) continue
    switch (field.tagName) {
      case 'INPUT':
        if (field.type === 'hidden') continue
        if (field.type === 'password') {
          field.value = '!123456qW'
        } else if (/email/i.test(field.name)) {
          field.value =
            Math.random().toString(36).slice(2, 8) +
            '@' +
            choice(['gmail.com', 'yahoo.com', 'outlook.com'])
        } else {
          field.value = choice([
            'qqqqq',
            'foobar',
            'qwerty',
            'test',
            'xyest',
            'penis',
            'hentai',
            'archbtw',
          ])
        }
        break
      case 'TEXTAREA':
        field.value = choice([
          'some text goes here',
          'i am fuzzzzzzzzzzy',
          'arch linux for pedophiles',
        ])
        break
      case 'SELECT':
        field.selectedIndex = 0
        break
    }
  }
}

// unused
function sendForm(form) {
  let params = { method: form.method }
  let url = form.action
  let data = new URLSearchParams(new FormData(form))
  if (form.method === 'get') {
    url += (~url.indexOf('?') ? '&' : '?') + data
  } else {
    params.body = data
  }
  return fetch(url, params)
}

;(() => {
  for (let form of document.forms) {
    fillFields(form)
    // sendForm(form)
    form.submit()
  }
})()
