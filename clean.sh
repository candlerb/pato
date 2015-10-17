#!/bin/sh
find . -name '*~' -print0 | xargs -0 rm -f
find . -name '*.pyc' -print0 | xargs -0 rm -f
find . -name '*,cover' -print0 | xargs -0 rm -f
rm -f .coverage
