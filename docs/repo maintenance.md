# Repository maintenance
## Setting up a dev environment
0. Clone the git repo <br> `$ git clone git@github.com:Stepland/jubeatools.git`
0. Install a recent version of Python (currently 3.8 is enough)
0. Install [poetry](https://python-poetry.org/) (jubeatools uses poetry to deal with many aspects of the project's life-cycle)
0. Install jubeatools (with dev dependencies) <br> `$ poetry install`
0. Run the tests <br> `$ poetry run pytest`
0. If everything went well you can now use jubeatools's commandline <br> `$ poetry run jubeatools`

## Making a new release
Sanity checks before anything serious happens, from the repo's root :
1. Run mypy and fix **all** the errors <br> `$ poetry run mypy .`
1. Format the code <br> `$ poetry run sh ./utils/format_code.sh`
1. Make sure the unit tests pass <br> `$ poetry run pytest`

Now that this is done you can move on to actually making a new version,
while still being in the repo's root :
1. Update `CHANGELOG.md`
1. Commit everything you want in the new release, including the changelog
1. Run the script <br> `$ poetry run python utils/bump_version.py {rule}`
   
   `{rule}` will usually be one of `patch`, `minor` or `major`. But it can be anything `poetry version` handles.

   Add `--commit` to let the script create the commit and tag for you as well
1. Inspect the result for mistakes
1. (If you did not use `--commit`)
    - Commit the version-bumped files
    - Add a tag with the format `vX.Y.Z` (don't forget the `v` at the start)
1. Push the version bump commit and the tag
1. Build & publish <br> `$ poetry publish --build`
