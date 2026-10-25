# Visitor-owned CSV workflows

`ingestion.py` enforces file, row, column and request bounds; `service.py` computes source-derived checked results; `api.py` serves the own-data workspace and explicit endpoints. No upload is written to shared application history. See [user-data contracts](../../../../docs/product/USER-DATA.md).
