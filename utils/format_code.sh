# find all files with unused imports, then hand them off to autoimport
flake8 \
    --isolated \
    --select=F401 \
    --format='%(path)s' \
    --exclude=__init__.py \
| sort \
| uniq \
| xargs autoimport

# auto-sort imports in all files
isort -y

# format code
black jubeatools