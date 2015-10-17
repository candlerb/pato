#!/bin/sh
header="from __future__ import absolute_import, division, print_function, unicode_literals"

for d in pato test libtest examples; do
  find "$d" -name '*.py' | while read f; do
    if [ -s "$f" ]; then
      if ! grep "^$header\$" "$f" >/dev/null; then
        echo "Missing header: $f"
        echo "$header"
      fi
    fi
    # Whitespace at end of lines
    if grep "[[:blank:]]$" "$f" >/dev/null; then
     echo "sed -E -i -e 's/[[:blank:]]+$//' '$f'"
    fi
  done
done

# Check for duplicate test names
for d in test; do
  find "$d" -name 'test_*.py' | xargs grep '^def test_' | cut -f1 -d'(' | sort | uniq -c | grep -v ' 1 '
done
