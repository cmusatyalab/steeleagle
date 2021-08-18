cd react
npm run build
cd ../flask
gunicorn -b :8080 -k gevent -w 1 api:app
