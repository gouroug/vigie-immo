bind = "127.0.0.1:5000"
workers = 4
timeout = 120          # /api/analyze appelle plusieurs APIs externes (30-60 s)
accesslog = "-"        # stdout → journald
errorlog = "-"
loglevel = "info"
