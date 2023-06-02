#!/bin/bash
for (( i=1; i <= 100; i++)); do
  echo "current page: $i" >&2
  output=$(curl -A 'Mozilla/5.0' -s 'https://themanifest.com/it-services/companies?page='$i | htmlq --attribute href '.provider-card__visit-btn.provider-visit.track-website-visit' | sed -r 's/\?utm.*//' | uniq)
  links=$(wc -l <<< "$output")
  echo "links on page: $links" >&2
  echo "$output"
  if [[ $links -lt 30 ]]; then
    break
  fi
done
