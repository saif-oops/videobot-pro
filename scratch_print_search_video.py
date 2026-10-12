content = open('flow_app.js', 'r', encoding='utf-8').read()
pos = content.find('/searchVideo')
print(content[pos-200:pos+1200])
