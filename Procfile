web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --threads 4 --worker-class gthread --worker-tmp-dir /dev/shm --timeout 30 --keep-alive 5 --access-logfile - --error-logfile -
