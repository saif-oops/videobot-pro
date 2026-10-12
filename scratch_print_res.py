content = open('flow_app.js', 'r', encoding='utf-8').read()
pos = content.find("res['file_name']")
print(content[pos:pos+1500])
