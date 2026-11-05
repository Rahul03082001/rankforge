#!/bin/sh
set -eu
profile="${1:-fixture}"
if [ "$profile" = fixture ]; then
  python -m rankforge.cli fixture --data data/fixture
  source_dir=data/fixture
else
  python -m rankforge.cli download --data data
  source_dir=data/fiqa
fi
python -m rankforge.cli audit --data "$source_dir"
python -m rankforge.cli index --data "$source_dir" --output "artifacts/$profile"
python -m rankforge.cli train --data "$source_dir" --bundle "artifacts/$profile" --output "artifacts/$profile-ltr"
python -m rankforge.cli evaluate --data "$source_dir" --bundle "artifacts/$profile-ltr" --split dev --output "reports/$profile-dev-evaluation.json"
python -m rankforge.cli freeze --bundle "artifacts/$profile-ltr" --output "reports/$profile-frozen.json"
python -m rankforge.cli evaluate --data "$source_dir" --bundle "artifacts/$profile-ltr" --split test --frozen "reports/$profile-frozen.json" --output "reports/$profile-test-evaluation.json"
