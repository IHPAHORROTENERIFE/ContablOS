# ContabOS v1.0.2-test

Primera versión cliente-servidor para asesoría/outsourcing contable.

## Ejecutar

```bash
cd //M3/py/contablOS
pip install -r requirements.txt
python scripts/run_server.py
```

Abrir: http://localhost:8000

## Variables opcionales

```bash
set GOCARDLESS_SECRET_ID=...
set GOCARDLESS_SECRET_KEY=...
set CONTABLOS_PUBLIC_BASE_URL=http://localhost:8000
set IONOS_API_KEY=...
set IONOS_MAILBOX_ENDPOINT=https://endpoint-contrato-ionos/mailboxes
```

## Novedades v1.0.2-test

- Integración GoCardless Bank Account Data.
- Descarga de movimientos bancarios vía PSD2/AISP.
- Dashboard bancario.
- Conciliación automática y generación de propuesta de asiento.
- Provisioning/registro de cuentas IONOS email.
- CRM y multicuenta email.

## Copiar a destino

Copiar la carpeta `contablOS` a:

```text
//M3/py/contablOS
```
