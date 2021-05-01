import argparse
import subprocess

import toml

parser = argparse.ArgumentParser()
parser.add_argument(
    "rule",
    help="either a semver string or a bump rule, will be passed to poetry",
)
args = parser.parse_args()

subprocess.run(["poetry", "version", args.rule], check=True)

with open("pyproject.toml") as f:
    pyproject = toml.load(f)

version = pyproject["tool"]["poetry"]["version"]

with open("jubeatools/version.py", mode="w") as f:
    f.write(f'__version__ = "{version}"\n')
