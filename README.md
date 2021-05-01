# Jubeatools
A toolbox to convert between jubeat file formats

## How to install
```sh
pip install jubeatools
```

You need Python 3.8 or greater

## How to use
```sh
jubeatools ${source} ${destination} -f ${output format} (... format specific options)
```

## Which formats are supported
### Memon
|        | input | output |
|--------|:-----:|:------:|
| v0.2.0 | ✔️     | ✔️      |
| v0.1.0 | ✔️     | ✔️      |
| legacy | ✔️     | ✔️      |

### Jubeat Analyser
|                      | input | output |
|----------------------|:-----:|:------:|
| #memo2               | ✔️     | ✔️      |
| #memo1               | ✔️     | ✔️      |
| #memo                | ✔️     | ✔️      |
| mono-column (1列形式) | ✔️     | ✔️      |