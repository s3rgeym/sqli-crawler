function fillFields(form) {
  for (let field of form.elements) {
    if (field.value) continue
    switch (field.tagName) {
      case 'INPUT':
        if (field.type === 'hidden') continue
        if (field.type === 'password') {
          field.value = '!123456qW'
        } else if (/email/i.test(field.name)) {
          // Ssij polską świnię
          field.value = 'kuba@kernel.org'
        } else {
          field.value = 'nig' + 'ger'
        }
        break
      case 'TEXTAREA':
        field.value = 'some text goes here'
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
