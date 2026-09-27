# Visitor-owned data workflows

`imports.py` normalizes CSV, TSV, Excel, JSON and JSONL files; `ingestion.py` enforces file, row, column and request bounds; `service.py` computes source-derived checked results; `stream.py` delivers server-sent progress; `signing.py` attests completed reports; `api.py` serves the own-data workspace and its endpoints. No upload is written to shared application history. See [data imports](../../../../docs/product/DATA-IMPORTS.md).
