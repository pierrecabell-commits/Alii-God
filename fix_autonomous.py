with open('Alii_redhat_fixed.py') as f:
cat > fix_Alii.py << 'HEREDOC'
lines = open('Alii_redhat_fixed.py').readlines()
out = []
skip_exec = False
i = 0
while i < len(lines):
    # Skip the manual exec handler
    if 'if msg.lower() == ' in lines[i] and 'exec' in lines[i] and 'last_code_blocks' in lines[i]:
        skip_exec = True
    if skip_exec:
        if 'continue' in lines[i]:
            skip_exec = False
        i += 1
        continue
    # Replace code block detection with auto-execution
    if 'code_blocks = extract_code_blocks' in lines[i]:
        out.append(lines[i])
        # Skip the old if code_blocks block
        i += 1
        while i < len(lines) and 'except KeyboardInterrupt' not in lines[i]:
            if 'if code_blocks:' in lines[i]:
                # Insert new autonomous execution code
                out.append('            if code_blocks:\n')
                out.append('                print(f' + chr(39) + '\\n[AUTO-EXECUTING {len(code_blocks)} code block(s)...]' + chr(39) + ')\n')
                out.append('                for i, block in enumerate(code_blocks):\n')
                out.append('                    if block[' + chr(39) + 'type' + chr(39) + '] in [' + chr(39) + 'python' + chr(39) + ', ' + chr(39) + 'bash' + chr(39) + ', ' + chr(39) + 'sh' + chr(39) + ']:\n')
                out.append('                        print(f' + chr(39) + '\\n--- Executing block {i+1} ({block[' + chr(34) + 'type' + chr(34) + ']}) ---' + chr(39) + ')\n')
                out.append('                        output = execute_code(block[' + chr(39) + 'code' + chr(39) + '], block[' + chr(39) + 'type' + chr(39) + '])\n')
                out.append('                        print(f' + chr(39) + 'Output:\\n{output}' + chr(39) + ')\n')
                out.append('                        print(f' + chr(39) + '--- End block {i+1} ---' + chr(39) + ')\n')
                out.append('                        memory.add_memory(' + chr(34) + 'context' + chr(34) + ', f' + chr(34) + 'Executed: {output[:200]}' + chr(34) + ')\n')
                # Skip old lines until we hit except
                i += 1
                while i < len(lines) and 'except KeyboardInterrupt' not in lines[i]:
                    i += 1
                break
            i += 1
        continue
    out.append(lines[i])
    i += 1
result = ''.join(out)
result = result.replace('Alii with Memory - Code Execution Enabled', 'Alii AUTONOMOUS MODE - Auto-Execute Enabled')
result = result.replace('exec' + chr(34) + ' to run code from last response', 'Code blocks AUTO-EXECUTE immediately')
result = result.replace('last_code_blocks = []', '')
with open('Alii_autonomous.py', 'w') as f:
    f.write(result)
print('✓ Created Alii_autonomous.py')
HEREDOC



python3 fix_Alii.py

