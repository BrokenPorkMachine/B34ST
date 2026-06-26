# B34ST Unified Multi-Tool Task List

- [x] Create b34stool.py with:
  - [x] Session class for artifact directory management
  - [x] Colors class for TTY-aware output
  - [x] Timing/instrumentation helpers
  - [x] 13 category menu functions
  - [x] run_and_log() subprocess wrapper
  - [x] Interactive and non-interactive modes

- [x] Add top-level menu with categories:
  - [x] System menu (status, build, test)
  - [x] Device menu (info, detect, console)
  - [x] USBliter8 menu (pwn-and-inspect, jailbreak)
  - [x] IPSW menu (catalog, download, upgrade)
  - [x] Boot Image menu (build, inspect, send)
  - [x] Deployment menu (deploy, recover, inspect)
  - [x] Hardware menu (prepare, bringup)
  - [x] Session menu (status, tools)
  - [x] Validation menu (session, evidence)
  - [x] Release menu (package, gate)
  - [x] Module menu (status, upload, run)
  - [x] Research Runtime menu (guided, validate)
  - [x] B34ST menu (environment, info)

- [x] Wire into fbr34ker:
  - [x] Add "b34stool" command in fbr34ker
  - [x] Add handler to dispatch to b34stool.py

- [x] Make executable and verify:
  - [x] chmod +x b34stool.py
  - [x] python -m py_compile b34stool.py
