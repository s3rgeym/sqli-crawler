;(doc => {
  const choice = arr => arr[(Math.random() * arr.length) | 0]

  // https://stackoverflow.com/tags
  // $$('.post-tag').map(a => a.innerText).filter(a => /^[a-z]+$/.test(a))
  const soTags = [
    'javascript',
    'python',
    'java',
    'php',
    'android',
    'html',
    'jquery',
    'css',
    'ios',
    'sql',
    'mysql',
    'r',
    'reactjs',
    'arrays',
    'c',
    'json',
    'swift',
    'django',
    'angular',
    'pandas',
    'excel',
    'angularjs',
    'regex',
    'ruby',
    'linux',
    'ajax',
    'iphone',
  ]

  // https://www.pornhub.com/video?o=tr
  // $$('span.title').map(span => span.innerText.trim()).filter(title => title.split(' ').length > 3)
  const pornHubTitles = [
    'TUTORIAL 2 Teoria y práctica de como comer un coño en mi experiencia 👅💦',
    'StepSis Paid with Deep Blowjob to He Drive Her Home, Part 2 (Sloppy Blowjob, Throatpie)',
    'Attempt to Spice Up The Relationship Turned Out into Pussy Creampie',
    '【Naimi Tiktok Series】Naked tiktok dance collection 1 - 奶咪抖音系列1',
    'TEEN & PETITE VS BIG COCK',
    'he fucks my pussy sideways until he cum',
    'Sexy woman in heels and cocktail dress fucks her ass and tight pussy',
    'セックス瞑想を初体験してみたら潮吹きアクメが止まらず最後は中出し射精しちゃった Japanese Amateur Meditation SEX Cumshot HD - えむゆみカップル',
    '"Oksana is watching TV, a lot of sperm, fucking in the mouth, throat blowjob" _ NIGONIKA',
    "Convinced Stepsister Fuck While Parents Aren't Home - Via Hub",
    'STEPSISTER ASKED TO LOSE VIRGINITY',
    'Girlfriend and her friend fucked Wednesday',
    'I came to the library to read, and instead of knowledge I got a dick',
    "Fit Teen Fucked at Bird's Eye View. Part II",
    'INCREDIBLE BLOWJOB COMPILATION #3',
    "Fucked my mom's friend's daughter on the cruise",
    'Изменил девушке с ее лучшей подругой. отсосала член парню подруги пока она ходила в магазин.',
    'Students, Sushi, Fuck in the Kitchen ORGY3 _ 1winporn _ NIGONIKA BEST PORN 2023',
    '🔥 Hot Girl Compilation Full of Emotions and Cahoots',
    'Try not to cum inside my tight pussy after oiled Handjob. Cowgirl creampie',
    'Ep 4 - When a Horny Hotel Manager Puts Her Pussy On Your Face After Masturbating - NicoLove',
    'FUCK ME SMOKING CBD ESPAÑOLA CULONA, Cums in my face and i play with the cum ^*^',
    '🔥Neighbor Wants My Dick While Husband Is On A Business Trip',
    'a beautiful blonde masturbates in the pool and lures a peeping guy into a blowjob',
    'Hot Asian brunette fucks herself with big dildo and cums from vibrator',
    'Beautiful big ass brunette, her ass riding is from another world 🔥 - Miss Pasion',
    'Friday sex riding rodeo jumping delicious ass - LuxuryMur',
    'Fucked a juicy girl with fat ass in public sauna',
    'When you draw good threesome with anal',
    '1win Sports with friends turned into passionate fucking _ best orgy from NIGONIKA',
    'Johnny Sins - She Invited her Friend to FILM US!',
    'THROATPIE!! - SLIPPERY HOT BUSTY GF WANTS YOUR CUM AND SHE WILL TAKE IT FROM YOU',
    'Hot girl gives 69 deepthroat! Throatpie!',
    'Very JUICY SLUT fucked HARD in all holes and cum in THROAT CUM IN THROAT',
    'POV: he caught me masturbating. Sloppy blowjob & footjob in stockings',
    '"Cum in mouth" fucking with my girlfriend\'s boyfriend threesome _ NIGONIKA TOP PORN 2023',
    'He begged me for it, I had to fuck his ass until the sperm poured.',
  ]

  const fullNames = [
    'Adam Smith',
    'Adolf Hitler',
    'Vladimir Putin',
    'Barack Obama',
    'Mohammed Ali',
  ]

  const firstNames = []
  const lastNames = []
  for (let name of fullNames) {
    let words = name.split(' ')
    firstNames.push(words.shift())
    lastNames.push(words.join(' '))
  }

  function fillAndSubmit(form) {
    for (let field of form.elements) {
      if (field.value) continue
      switch (field.tagName) {
        case 'INPUT':
          if (field.type === 'hidden' || field.type === 'file') continue
          if (field.type === 'password') {
            field.value = '!123456qW'
          } else if (/email/i.test(field.name)) {
            field.value =
              Math.random().toString(36).slice(2) +
              '@' +
              choice(['gmail.com', 'yahoo.com', 'outlook.com'])
          } else if (/^fisrt_?name$/i.test(field.name)) {
            field.value = choice(firstNames)
          } else if (/^(last|second)_?name$/i.test(field.name)) {
            field.value = choice(lastNames)
          } else {
            let tag = choice(soTags)
            field.value = tag.length >= 5 ? tag : (tag + '1234').slice(0, 5)
          }
          break
        case 'TEXTAREA':
          field.value = choice(pornHubTitles)
          break
        case 'SELECT':
          field.selectedIndex = 0
          break
      }
    }
    form.submit()
  }

  for (let f of doc.forms) {
    fillAndSubmit(f)
  }
})(document)
