# Launch Assets

## Installation

### pip
```bash
git clone https://github.com/<your-username>/developer_plane.git
cd developer_plane
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python src/main.py --scan D:\\Projects
python src/main.py --host 127.0.0.1 --port 8787
```

### Docker
```bash
docker build -t developer-plane .
docker run -p 8787:8787 -v %cd%:/app developer-plane
```

### Source
```bash
git clone https://github.com/<your-username>/developer_plane.git
cd developer_plane
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

## First-run demo

1. Start the server: `python src/main.py --host 127.0.0.1 --port 8787`
2. Open `http://127.0.0.1:8787`
3. Scan a folder with projects, e.g. `D:\Projects`
4. Run **Analyze All** to generate `project_status.md` in each project
5. Open a project detail to see genome, stage, and recent signals
6. Enable **Autopilot** on a project to queue an agent run
7. Review the proposal, then approve or discard
8. If discarded, files are automatically reverted

## Troubleshooting

1. **Port 8787 already in use**: change port with `--port 8788`
2. **Database locked**: close other running instances of the server
3. **Watcher misses events on Windows**: run from WSL2 or watch fewer roots
4. **Agent run fails**: check `DCP_AGENT_CMD` and that the agent CLI is installed
5. **Scan is slow**: reduce `max_depth` in discovery or exclude large system folders
