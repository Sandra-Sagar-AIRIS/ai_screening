import re

def resolve():
    file_path = r'c:\Users\Aravind\Desktop\AIRIS_Project\AIRIS\frontend\components\dashboard-shell.tsx'
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    new_text = re.sub(
        r'<<<<<<< HEAD\n([\s\S]*?)=======\n[\s\S]*?>>>>>>> [a-f0-9]+\n?',
        r'\1',
        text
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)

resolve()
