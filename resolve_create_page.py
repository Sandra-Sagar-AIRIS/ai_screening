import re

def resolve():
    file_path = r'c:\Users\Aravind\Desktop\AIRIS_Project\AIRIS\frontend\app\(dashboard)\candidates\create\page.tsx'
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # We will replace all conflict blocks by keeping HEAD.
    # The pattern is <<<<<<< HEAD\n(HEAD_CONTENT)=======\n(MAIN_CONTENT)>>>>>>> [commit_hash]\n
    
    # We want to replace each match with HEAD_CONTENT.
    # We need to be careful not to match across multiple conflict blocks.
    # So we use non-greedy matching: (.*?)
    
    new_text = re.sub(
        r'<<<<<<< HEAD\n([\s\S]*?)=======\n[\s\S]*?>>>>>>> [a-f0-9]+\n?',
        r'\1',
        text
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)

resolve()
