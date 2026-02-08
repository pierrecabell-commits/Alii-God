#!/usr/bin/env python3
import json, requests, sys
c=json.load(open("config.json"))
p=c["perplexity"]
q=" ".join(sys.argv[1:]) or input("Search: ")
r=requests.post(f"{p['base_url']}/chat/completions",headers={"Authorization":f"Bearer {p['api_key']}","Content-Type":"application/json"},json={"model":p["model"],"messages":[{"role":"system","content":"Alii AI assistant"},{"role":"user","content":q}]})
print("\n"+r.json()["choices"][0]["message"]["content"]+"\n")
