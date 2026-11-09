"""Decodifica o arquivo tool-results gerado pelo javascript_tool (JSON em string) e salva como JSON.

Uso: python3 collector/local/save_chunk.py <tool-result.txt> <saida.json>
"""
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
txt = d[0]["text"] if isinstance(d, list) else d["text"]
i = txt.rfind('"\n\n(captured')
s = txt[: i + 1] if i > 0 else txt
arr = json.loads(json.loads(s))
json.dump(arr, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
print(len(arr), arr[0]["id"], arr[-1]["id"])
