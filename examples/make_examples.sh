#! /bin/sh

find . ! -path . -type d | while read -r directory
do
  file="$(basename "$directory").pdf"
  cd "$directory"
  echo "$file"
  ./make_example.sh
  mv talk.pdf "../$file"
  cd ..
done
