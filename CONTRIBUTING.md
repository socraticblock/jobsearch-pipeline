# Contributing

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install build
```

## Running tests

```bash
python3 -m unittest discover -s tests
```

## Building

```bash
python3 -m build
```

## Privacy

This project handles personal data. Never commit real candidate profiles,
job ledgers, or credentials. Use synthetic fixtures only.

## License

By contributing, you agree that your contributions will be licensed under
the MIT License.
