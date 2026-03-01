module.exports = {
  apps: [
    {
      name: 'GEMINI_BOT',
      script: 'src/main.py',
      cwd: '/home/arun/.openclaw/workspace/AI-Sentinel-Scalper',
      interpreter: '/home/arun/.openclaw/workspace/AI-Sentinel-Scalper/.venv/bin/python',
      env: {
        PYTHONPATH: '.',
        AUTONOMOUS_SOAK: 'true',
        OVERNIGHT_AUDIT_LOG: '/home/arun/.openclaw/workspace/AI-Sentinel-Scalper/logs/overnight_audit.log',
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 2000,
    },
    {
      name: 'GEMINI_GUARD',
      script: 'src/guardian.py',
      cwd: '/home/arun/.openclaw/workspace/AI-Sentinel-Scalper',
      interpreter: '/home/arun/.openclaw/workspace/AI-Sentinel-Scalper/.venv/bin/python',
      env: {
        PYTHONPATH: '.',
        AUTONOMOUS_SOAK: 'true',
        OVERNIGHT_AUDIT_LOG: '/home/arun/.openclaw/workspace/AI-Sentinel-Scalper/logs/overnight_audit.log',
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 2000,
    },
    {
      name: 'GEMINI_DASH',
      script: '/home/arun/.openclaw/workspace/AI-Sentinel-Scalper/.venv/bin/python',
      args: '-m streamlit run dashboard.py --server.headless true --server.port 8501',
      cwd: '/home/arun/.openclaw/workspace/AI-Sentinel-Scalper',
      env: {
        PYTHONPATH: '.',
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 2000,
    },
  ],
};
