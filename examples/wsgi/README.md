Another way to run this app is under gunicorn: e.g. for four pre-forked
worker processes:

~~~
pip install gunicorn
gunicorn run:app -w 4 -b 0.0.0.0:4567
~~~
