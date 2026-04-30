# ContabOS v1.0.2-test — Bancos, conciliación, CRM e IONOS

## 1. Agregador bancario recomendado

Se integra **GoCardless Bank Account Data** como agregador base para PSD2/AISP. La API permite crear consentimientos, redirigir al cliente a su banco y descargar cuentas/movimientos tras la autorización.

Variables necesarias:

```bash
set GOCARDLESS_SECRET_ID=tu_secret_id
set GOCARDLESS_SECRET_KEY=tu_secret_key
set CONTABLOS_PUBLIC_BASE_URL=http://localhost:8000
```

## 2. Flujo de conexión bancaria

1. En ContabOS: Bancos → Conectar GoCardless.
2. Indicar sociedad e `institution_id`.
3. El backend crea una `requisition`.
4. Se devuelve `consent_link`.
5. El cliente abre el enlace, entra en su banco y autoriza.
6. Volver a ContabOS y pulsar sincronizar.
7. Los movimientos se guardan en `bank_movements`.
8. El indexador propone asiento: por ejemplo ENDESA → GASTO_LUZ → 628.

Endpoints clave:

```text
GET  /api/banking/gocardless/institutions?country=ES
POST /api/banking/gocardless/connect
POST /api/banking/connections/{connection_id}/sync
GET  /api/banking/movements/{company_id}
GET  /api/banking/dashboard/{company_id}
POST /api/banking/reconcile/auto-entry
```

## 3. Dashboard bancario

Calcula:

```text
movimientos importados
pendientes de conciliación
cobros
pagos
flujo neto
clasificación por asiento tipo
```

## 4. Conciliación automática + asiento

El endpoint `/api/banking/reconcile/auto-entry` genera una propuesta de asiento desde un movimiento bancario.

Ejemplo pago de luz:

```text
628 Suministros                 Debe
472000 IVA soportado estimado   Debe
572 Banco                       Haber
```

Queda en estado `PROPUESTO` para revisión.

## 5. IONOS: creación/configuración de cuentas

Se añadió un módulo de provisión de cuentas IONOS:

```text
POST /api/ionos/email-accounts
GET  /api/ionos/email-accounts
```

Por defecto registra la cuenta en ContabOS y configura SMTP/IMAP:

```text
SMTP: smtp.ionos.es:587
IMAP: imap.ionos.es:993
```

Para creación real por API, configure:

```bash
set IONOS_API_KEY=...
set IONOS_MAILBOX_ENDPOINT=https://...
```

Nota técnica: la documentación pública de IONOS consultada expone APIs para hosting, DNS, dominios y SSL. La creación programática de buzones depende del producto contratado y del endpoint habilitado en la cuenta. Por eso el prototipo deja una capa adaptable mediante `IONOS_MAILBOX_ENDPOINT`.

## 6. CRM interno

Módulos incluidos:

```text
crm_contacts
email_accounts
crm_messages
ionos_accounts
```

Permite preparar comunicaciones, asignarlas a cliente/sociedad y dejar cola de envío. En producción debe añadirse cifrado de credenciales, OAuth donde sea posible y logs de auditoría.
