#!/bin/sh
# add '-s' to skip Zarr .attrs file checks

echo "Validating all local sample-data:"
ls -1d tests/sample-data/*/*.zarr
echo

for f in tests/sample-data/*/*.zarr
do 
  model=models/$(basename $(dirname $f))
  echo "$(date +%FT%T) validating $f with $model"
  python3 eopf_qa/eopf_zarr_qa.py validate --model=$model --zarr $f $*
  echo
done
