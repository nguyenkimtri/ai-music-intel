module.exports = {
  apps: [
    {
      name: 'music-backend',
      script: './backend/index.js',
      cwd: './',
      env: {
        NODE_ENV: 'production',
        PORT: 8000
      }
    },
    {
      name: 'music-worker',
      script: 'python3',
      args: './worker/main.py',
      cwd: './',
      interpreter: 'none',
      env: {
        PYTHONPATH: './'
      }
    }
  ]
};
