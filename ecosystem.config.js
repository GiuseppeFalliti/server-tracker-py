module.exports = {
  apps: [
    {
      name: "tracker-tcp-server",
      script: "main.py",
      cwd: "c:\\Users\\Admin\\Desktop\\server_tracker\\server_py",
      interpreter: "c:\\Users\\Admin\\Desktop\\server_tracker\\server_py\\.venv\\Scripts\\python.exe",
      autorestart: true,
      watch: false,
      time: true,
      error_file: "c:\\Users\\Admin\\Desktop\\server_tracker\\server_py\\pm2-logs\\tracker-tcp-server-error.log",
      out_file: "c:\\Users\\Admin\\Desktop\\server_tracker\\server_py\\pm2-logs\\tracker-tcp-server-out.log",
      merge_logs: true,
      env: {
        PM2_HOME: "c:\\Users\\Admin\\Desktop\\server_tracker\\server_py\\pm2-home"
      }
    }
  ]
};
