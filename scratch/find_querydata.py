with open("/Users/diegoh/.gemini/antigravity/brain/73b6df1c-1df2-4829-ac61-6a8301d2875b/.system_generated/tasks/task-327.log", "r", encoding="utf-8") as f:
    logs = f.read()

print("Logs length:", len(logs))

import re
print("\nSearching for requests matching 'querydata' or similar...")
matches = re.findall(r'(-> Req:.*?(?:querydata|wabi|api|data|models).*?)\n', logs, re.IGNORECASE)
print(f"Found {len(matches)} matching request logs.")
for m in matches[:30]:
    print("-", m)

print("\nSearching for all -> Req: lines in the log:")
req_lines = [line for line in logs.split("\n") if "-> Req:" in line]
print(f"Total requests: {len(req_lines)}")
for req in req_lines[:30]:
    print(" ", req[:120])
