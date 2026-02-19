# jsonmin

Show the structure of any JSON document and generate copy-pasteable [`jq`](https://jqlang.org/) paths. Useful for large API responses during pentesting or development.

- Color-coded tree: keys, types, array lengths, sample values
- `--paths`: flat list of jq leaf paths
- Handles nested objects, mixed-type arrays, primitive roots
- Auto-quotes unsafe jq keys (GUIDs, spaces, dots, etc.)
- Reads from file or stdin — zero dependencies (Python 3.8+ stdlib)

## Examples

```bash
# tree view
jsonmin.py response.json

# flat jq paths
jsonmin.py --paths response.json

# pipe from curl
curl -s https://api.example.com/data | jsonmin.py --paths
```

```
Root: object

  id           string    "a3f9c..."
  name         string    "John Doe"
  active       boolean   true
  tags         array(3)
    [0]        string    "admin"
  address      object
    city       string    "Springfield"
```

## Install

```bash
git clone https://github.com/sikumy/jsonmin.git
cd ./jsonmin/
chmod +x jsonmin/jsonmin.py
python jsonmin.py
```

## Tests

```bash
python3 test_jsonmin.py   # 50 edge cases, requires jq
```
