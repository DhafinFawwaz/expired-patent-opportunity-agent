# How to run patentic. Record with: vhs docs/demo/demo.tape (from the repo root).
Output docs/demo/demo.mp4

Set Shell "zsh"
Set FontSize 15
Set Width 1400
Set Height 860
Set TypingSpeed 25ms
Set Padding 16

Hide
Type "setopt interactivecomments; rm -rf outputs/runs/video-demo outputs/runs/video-replay outputs/runs/video-outage; export PS1='$ '; clear" Enter
Show

Type "# 1. Install the workspace and create .env (no keys needed for the demo or the replay)" Enter
Sleep 500ms
Type "uv sync -q && cp -n .env.example .env; echo ready" Enter
Sleep 4s

Type "# 2. Offline demo: six synthetic patents, and you answer the two gates" Enter
Sleep 500ms
Type "uv run patentic demo --no-llm --thread-id video-demo" Enter
Wait+Line@60s /Plan \[/
Sleep 1500ms
Type "approve" Enter
Wait+Line@60s /Candidates \[/
Sleep 2500ms
Type "accept" Enter
Wait@60s /^\$\s*$/
Sleep 3s

Type "clear" Enter
Type "# 3. The files a run writes" Enter
Type "ls outputs/runs/video-demo" Enter
Sleep 3s

Type "# 4. Rerun the committed real result offline, with its recorded model answers" Enter
Sleep 500ms
Type "uv run patentic run --replay --decisions fixtures/decisions/approve-all.yaml --thread-id video-replay" Enter
Wait@120s /^\$\s*$/
Sleep 3s

Type "clear" Enter
Type "uv run patentic cost video-replay" Enter
Sleep 4s

Type "# 5. Simulate a Gazette outage: the run records it and still writes both files" Enter
Sleep 500ms
Type "uv run patentic run --offline --no-llm --simulate-outage og --decisions fixtures/decisions/approve-all.yaml --thread-id video-outage" Enter
Wait@120s /^\$\s*$/
Sleep 3s

Type "clear" Enter
Type "# 6. A live run needs GOOGLE_CLOUD_PROJECT in .env and gcloud application-default login" Enter
Type "# make run          (first run scans about 44 GB of the BigQuery free tier; a same-day rerun scans 0)" Enter
Type "# patentic resume <run id>   continues a run stopped at a gate" Enter
Type "# make check        lint, mypy --strict and the offline test suite" Enter
Sleep 6s
