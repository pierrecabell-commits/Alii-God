from datetime import timezone
import subprocess
import sys
import os
import tempfile

SYSTEM_PROMPT = """You are Alii, a local AI assistant running on AliiLLM (llama3.2:3b model) on the user's own hardware.

You have these capabilities:
1. Answer questions and have conversations
2. Write and execute Python code when asked
3. Execute terminal commands when needed
4. Help with coding, system administration, and technical tasks

When the user asks you to write code:
- Generate the code clearly
- Mark code blocks with ```python or ```bash
- Explain what the code does

IMPORTANT: You ARE running locally on this machine. AliiLLM is real and you are powered by it. Do not claim to be cloud-based."""

def extract_code_blocks(text):
    blocks = []
    lines = text.split('\n')
    in_block = False
    current_block = []
    block_type = None

    for line in lines:
        if line.strip().startswith('```'):
            if in_block:
                blocks.append({'type': block_type, 'code': '\n'.join(current_block)})
                current_block = []
                in_block = False
            else:
                in_block = True
                block_type = line.strip()[3:].lower() or 'text'
        elif in_block:
            current_block.append(line)

    return blocks

def execute_code(code, lang='python'):
    if lang == 'python':
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name

            result = subprocess.run(['python3', temp_file], capture_output=True, text=True, timeout=30)
            os.unlink(temp_file)
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"Error: {str(e)}"

    elif lang in ['bash', 'sh']:
        try:
            result = subprocess.run(code, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"Error: {str(e)}"

    return "Unsupported language"

def chat():
    print('=' * 60)
    print('Alii Advanced Chat - Code Execution Enabled')
    print('=' * 60)
    print('Commands:')
    print('  - Type normally to chat')
    print('  - Type "exec" to run code from last response')
    print('  - Type "exit" to quit')
    print('=' * 60)

    last_code_blocks = []

    while True:
        try:
            msg = input('\nYou: ')

            if msg.lower() in ['exit', 'quit', 'bye']:
                print('Goodbye!')
                break

            if msg.lower() == 'exec' and last_code_blocks:
                for block in last_code_blocks:
                    print(f'\n[Executing {block["type"]} code...]')
                    output = execute_code(block['code'], block['type'])
                    print(f'Output:\n{output}')
                continue

            full_prompt = f"{SYSTEM_PROMPT}\n\nUser: {msg}"

            result = subprocess.run(['AliiLLM', 'run', 'llama3.2:3b', full_prompt], capture_output=True, text=True, timeout=60)

            response = result.stdout.strip()
            print(f'\nAlii: {response}')

            code_blocks = extract_code_blocks(response)
            if code_blocks:
                last_code_blocks = code_blocks
                print(f'\n[Found {len(code_blocks)} code block(s). Type "exec" to run them]')

        except KeyboardInterrupt:
            print('\nGoodbye!')
            break
        except Exception as e:
            print(f'Error: {e}')

if __name__ == '__main__':
    chat()
