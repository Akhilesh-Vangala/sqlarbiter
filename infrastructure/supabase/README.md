# Account persistence

The [migration](migrations/001_product_workspace.sql) defines owner-isolated, immutable account snapshots with row-level security. [Setup, consent, and sessions](../../docs/product/PRODUCT-WORKSPACE.md#optional-cloud-accounts).

The policy check creates and drops its own random test database and needs an explicit administrative test URL:

```sh
SQLARBITER_PRODUCT_TEST_ADMIN_URL=postgresql://test-host/test-db python scripts/checks/product_rls.py
```

Use a disposable database for this script. The application needs only the HTTPS provider URL and the publishable key, and it refuses service-role keys.
