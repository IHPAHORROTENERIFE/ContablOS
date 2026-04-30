from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, date
import sqlite3, json, os, uuid, hashlib, requests

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / 'data' / 'contablos.sqlite3'
FRONTEND = BASE_DIR / 'frontend' / 'index.html'
GC_BASE_URL = os.getenv('GOCARDLESS_BASE_URL', 'https://bankaccountdata.gocardless.com/api/v2')
GC_SECRET_ID = os.getenv('GOCARDLESS_SECRET_ID', '')
GC_SECRET_KEY = os.getenv('GOCARDLESS_SECRET_KEY', '')
PUBLIC_BASE_URL = os.getenv('CONTABLOS_PUBLIC_BASE_URL', 'http://localhost:8000')
IONOS_API_BASE = os.getenv('IONOS_API_BASE', 'https://api.hosting.ionos.com')
IONOS_API_KEY = os.getenv('IONOS_API_KEY', '')

app = FastAPI(title='ContabOS v1.0.2-test', version='1.0.2-test')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def now(): return datetime.now().isoformat(timespec='seconds')
def norm(s): return (s or '').strip().lower()
def hash_secret(s): return hashlib.sha256((s or '').encode()).hexdigest() if s else None

DEFAULT_ACCOUNTS=[
('600','Compras de mercaderías','GASTO',None),('621','Arrendamientos y cánones','GASTO',None),('622','Reparaciones y conservación','GASTO',None),('623','Servicios profesionales independientes','GASTO',None),('624','Transportes','GASTO',None),('625','Primas de seguros','GASTO',None),('626','Servicios bancarios y similares','GASTO',None),('627','Publicidad, propaganda y RRPP','GASTO',None),('628','Suministros','GASTO',None),('629','Otros servicios','GASTO',None),('640','Sueldos y salarios','GASTO',None),('642','Seguridad Social empresa','GASTO',None),('681','Amortización inmovilizado material','GASTO',None),
('700','Ventas de mercaderías','INGRESO',None),('705','Prestaciones de servicios','INGRESO',None),('740','Subvenciones a la explotación','INGRESO',None),
('410','Proveedores','PASIVO',None),('430','Clientes','ACTIVO',None),('465','Remuneraciones pendientes de pago','PASIVO',None),('476','Organismos Seguridad Social acreedores','PASIVO',None),('572','Bancos','ACTIVO',None),('217','Equipos para procesos de información','ACTIVO',None),('281','Amortización acumulada inmovilizado material','PASIVO',None),
('472000','IVA soportado 21%','FISCAL','IVA_SOPORTADO'),('477000','IVA repercutido 21%','FISCAL','IVA_REPERCUTIDO'),('472010','IVA soportado 10%','FISCAL','IVA_SOPORTADO'),('477010','IVA repercutido 10%','FISCAL','IVA_REPERCUTIDO'),('472020','IVA soportado 4%','FISCAL','IVA_SOPORTADO'),('477020','IVA repercutido 4%','FISCAL','IVA_REPERCUTIDO'),
('472300','IGIC soportado 7%','FISCAL','IGIC_SOPORTADO'),('477300','IGIC repercutido 7%','FISCAL','IGIC_REPERCUTIDO'),('472310','IGIC soportado 3%','FISCAL','IGIC_SOPORTADO'),('477310','IGIC repercutido 3%','FISCAL','IGIC_REPERCUTIDO'),('472600','IPSI soportado Ceuta','FISCAL','IPSI_SOPORTADO'),('477600','IPSI repercutido Ceuta','FISCAL','IPSI_REPERCUTIDO'),('472700','IPSI soportado Melilla','FISCAL','IPSI_SOPORTADO'),('477700','IPSI repercutido Melilla','FISCAL','IPSI_REPERCUTIDO'),
('4750','Hacienda Pública acreedora por impuestos','FISCAL','HP_ACREEDORA'),('4700','Hacienda Pública deudora por impuestos','FISCAL','HP_DEUDORA'),('4751','HP acreedora retenciones','FISCAL','RETENCIONES'),
('631210','Impuesto especial hidrocarburos','FISCAL','IIEE_HIDROCARBUROS'),('475210','HP acreedora hidrocarburos','FISCAL','IIEE_HIDROCARBUROS'),('631230','Impuesto especial alcohol','FISCAL','IIEE_ALCOHOL'),('475230','HP acreedora alcohol','FISCAL','IIEE_ALCOHOL'),('631231','Impuesto cerveza','FISCAL','IIEE_CERVEZA'),('475231','HP acreedora cerveza','FISCAL','IIEE_CERVEZA'),('631240','Impuesto especial labores del tabaco','FISCAL','IIEE_TABACO'),('475240','HP acreedora tabaco','FISCAL','IIEE_TABACO')]
TEMPLATES=[
('GASTO_LUZ','Factura de luz / suministro eléctrico','GASTO','628','410','472000','luz,electricidad,suministro,endesa,iberdrola,naturgy,recibo luz','coste_energia'),('GASTO_AGUA','Factura de agua','GASTO','628','410','472000','agua,suministro agua,emmasa','coste_suministros'),('GASTO_ALQUILER','Alquiler','GASTO','621','410','472000','alquiler,renta,arrendamiento','coste_alquiler'),('GASTO_ASESORIA','Servicios profesionales','GASTO','623','410','472000','asesoria,abogado,notario,consultoria,gestoria','coste_profesionales'),('GASTO_BANCO','Comisión bancaria','GASTO','626','572',None,'comision,banco,cuota bancaria,mantenimiento cuenta','coste_bancario'),('COMPRA_ACTIVO_INFORMATICO','Compra de activo informático','ACTIVO','217','410','472000','ordenador,portatil,servidor,equipo informatico','capex'),('AMORTIZACION_ACTIVO','Amortización de activo','AMORTIZACION','681','281',None,'amortizacion,depreciacion','amortizacion'),('VENTA_SERVICIO','Venta de servicios','INGRESO','430','705','477000','factura emitida,servicio,venta servicio','ingresos_servicios'),('NOMINA','Nómina mensual','NOMINA','640','465',None,'nomina,salario,sueldo','coste_personal'),('SEGURO_SOCIAL_EMPRESA','Seguridad Social empresa','NOMINA','642','476',None,'seguridad social,seguros sociales','coste_personal'),('COBRO_CLIENTE','Cobro de cliente','TESORERIA','572','430',None,'cobro,transferencia cliente,ingreso banco','cobros'),('PAGO_PROVEEDOR','Pago a proveedor','TESORERIA','410','572',None,'pago proveedor,transferencia emitida,recibo domiciliado','pagos')]
GC_INSTITUTIONS=[('GOCARDLESS','GoCardless Bank Account Data','AISP PSD2 agregador autorizado','https://bankaccountdata.gocardless.com/api/v2','https://developer.gocardless.com/bank-account-data/overview','Gratis/low cost para AIS según plan; requiere secret_id/secret_key y consentimiento del cliente.')]

def init_db():
    con=db(); cur=con.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS managed_clients (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,client_type TEXT NOT NULL,service_model TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT,managed_client_id INTEGER NOT NULL,name TEXT NOT NULL,group_type TEXT NOT NULL,consolidated INTEGER DEFAULT 0,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY AUTOINCREMENT,managed_client_id INTEGER NOT NULL,group_id INTEGER,legal_name TEXT NOT NULL,tax_id TEXT,country TEXT DEFAULT 'ES',territory TEXT DEFAULT 'REGIMEN_COMUN',cnae TEXT,currency TEXT DEFAULT 'EUR',accounting_plan TEXT DEFAULT 'PGC_ES',consolidation_scope TEXT DEFAULT 'INDEPENDIENTE',created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER NOT NULL,code TEXT NOT NULL,name TEXT NOT NULL,account_type TEXT,tax_type TEXT,UNIQUE(company_id, code));
    CREATE TABLE IF NOT EXISTS accounting_templates (id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,operation_type TEXT NOT NULL,debit_account TEXT,credit_account TEXT,tax_account TEXT,keywords TEXT,kpi_tag TEXT);
    CREATE TABLE IF NOT EXISTS accounting_search_index (id INTEGER PRIMARY KEY AUTOINCREMENT,keyword TEXT NOT NULL,normalized_keyword TEXT NOT NULL,template_code TEXT NOT NULL,account_code TEXT NOT NULL,confidence_score REAL DEFAULT 0.90, UNIQUE(normalized_keyword,template_code));
    CREATE TABLE IF NOT EXISTS journal_entries (id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER NOT NULL,entry_date TEXT NOT NULL,description TEXT NOT NULL,status TEXT DEFAULT 'PROPUESTO',source TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS journal_lines (id INTEGER PRIMARY KEY AUTOINCREMENT,entry_id INTEGER NOT NULL,account_code TEXT NOT NULL,concept TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,tax_type TEXT,cost_center TEXT,third_party TEXT);
    CREATE TABLE IF NOT EXISTS kpi_events (id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER NOT NULL,kpi_tag TEXT NOT NULL,severity TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS crm_contacts (id INTEGER PRIMARY KEY AUTOINCREMENT,managed_client_id INTEGER,company_id INTEGER,contact_type TEXT DEFAULT 'CLIENTE',name TEXT NOT NULL,email TEXT,phone TEXT,notes TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS email_accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_user TEXT NOT NULL,display_name TEXT NOT NULL,email_address TEXT NOT NULL,provider TEXT DEFAULT 'SMTP_IMAP',smtp_host TEXT,smtp_port INTEGER DEFAULT 587,smtp_user TEXT,smtp_password TEXT,imap_host TEXT,imap_port INTEGER DEFAULT 993,use_tls INTEGER DEFAULT 1,active INTEGER DEFAULT 1,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS crm_messages (id INTEGER PRIMARY KEY AUTOINCREMENT,managed_client_id INTEGER,company_id INTEGER,contact_id INTEGER,email_account_id INTEGER,channel TEXT DEFAULT 'EMAIL',direction TEXT DEFAULT 'OUT',subject TEXT NOT NULL,body TEXT NOT NULL,status TEXT DEFAULT 'BORRADOR',related_document TEXT,created_at TEXT NOT NULL,sent_at TEXT);
    CREATE TABLE IF NOT EXISTS bank_api_providers (id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,psd2_platform TEXT,base_url TEXT,documentation_url TEXT,notes TEXT);
    CREATE TABLE IF NOT EXISTS bank_connections (id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER NOT NULL,provider_code TEXT NOT NULL,bank_institution_id TEXT,iban_alias TEXT,gocardless_requisition_id TEXT,consent_link TEXT,consent_status TEXT DEFAULT 'PENDIENTE',account_ids_json TEXT,environment TEXT DEFAULT 'SANDBOX',last_sync_at TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS bank_movements (id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER NOT NULL,bank_connection_id INTEGER,account_id TEXT,booking_date TEXT,value_date TEXT,concept TEXT,amount REAL,currency TEXT DEFAULT 'EUR',raw_json TEXT,suggested_template TEXT,suggested_account TEXT,reconciliation_status TEXT DEFAULT 'PENDIENTE',journal_entry_id INTEGER,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS bank_import_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT,bank_connection_id INTEGER NOT NULL,job_type TEXT DEFAULT 'AIS_TRANSACTIONS',status TEXT DEFAULT 'PENDIENTE',date_from TEXT,date_to TEXT,result_json TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS ionos_accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,owner_user TEXT,domain TEXT NOT NULL,local_part TEXT NOT NULL,email_address TEXT NOT NULL,password_hash TEXT,display_name TEXT,provider_response TEXT,status TEXT DEFAULT 'PENDIENTE',created_at TEXT NOT NULL);
    ''')
    con.commit(); con.close()

def seed():
    init_db(); con=db(); cur=con.cursor()
    for t in TEMPLATES:
        cur.execute('INSERT OR IGNORE INTO accounting_templates(code,name,operation_type,debit_account,credit_account,tax_account,keywords,kpi_tag) VALUES(?,?,?,?,?,?,?,?)', t)
        for kw in t[6].split(','):
            cur.execute('INSERT OR IGNORE INTO accounting_search_index(keyword,normalized_keyword,template_code,account_code,confidence_score) VALUES(?,?,?,?,?)',(kw.strip(),norm(kw),t[0],t[3],0.93))
    for p in GC_INSTITUTIONS:
        cur.execute('INSERT OR IGNORE INTO bank_api_providers(code,name,psd2_platform,base_url,documentation_url,notes) VALUES(?,?,?,?,?,?)', p)
    con.commit(); con.close()

def suggest_for_text(text):
    textn=norm(text)
    con=db(); rows=[dict(r) for r in con.execute('''SELECT i.template_code,i.account_code,t.name,t.debit_account,t.credit_account,t.tax_account,t.kpi_tag,i.confidence_score FROM accounting_search_index i JOIN accounting_templates t ON t.code=i.template_code WHERE ? LIKE '%' || i.normalized_keyword || '%' ORDER BY i.confidence_score DESC LIMIT 1''',(textn,))]; con.close()
    return rows[0] if rows else {'template_code':'PENDIENTE_CLASIFICAR','account_code':None,'confidence_score':0}

def gc_token():
    if not GC_SECRET_ID or not GC_SECRET_KEY:
        raise HTTPException(400, 'Faltan GOCARDLESS_SECRET_ID y GOCARDLESS_SECRET_KEY en variables de entorno')
    r=requests.post(f'{GC_BASE_URL}/token/new/', json={'secret_id':GC_SECRET_ID,'secret_key':GC_SECRET_KEY}, timeout=20)
    if r.status_code>=300: raise HTTPException(r.status_code, r.text)
    return r.json()['access']

def gc_headers(): return {'Authorization': f'Bearer {gc_token()}', 'Content-Type':'application/json'}

class ManagedClientIn(BaseModel): name:str; client_type:str='SOCIEDAD_SIMPLE'; service_model:str|None=None
class GroupIn(BaseModel): managed_client_id:int; name:str; group_type:str='GRUPO_EMPRESARIAL'; consolidated:bool=False
class CompanyIn(BaseModel): managed_client_id:int; group_id:int|None=None; legal_name:str; tax_id:str|None=None; country:str='ES'; territory:str='REGIMEN_COMUN'; cnae:str|None=None; consolidation_scope:str='INDEPENDIENTE'
class LineIn(BaseModel): account_code:str; concept:str=''; debit:float=0; credit:float=0; tax_type:str|None=None; cost_center:str|None=None; third_party:str|None=None
class EntryIn(BaseModel): company_id:int; entry_date:str; description:str; source:str='MANUAL'; lines:list[LineIn]
class CRMContactIn(BaseModel): managed_client_id:int|None=None; company_id:int|None=None; contact_type:str='CLIENTE'; name:str; email:str|None=None; phone:str|None=None; notes:str|None=None
class EmailAccountIn(BaseModel): owner_user:str='admin'; display_name:str; email_address:str; provider:str='SMTP_IMAP'; smtp_host:str|None=None; smtp_port:int=587; smtp_user:str|None=None; smtp_password:str|None=None; imap_host:str|None=None; imap_port:int=993; use_tls:bool=True; active:bool=True
class CRMMessageIn(BaseModel): managed_client_id:int|None=None; company_id:int|None=None; contact_id:int|None=None; email_account_id:int|None=None; channel:str='EMAIL'; direction:str='OUT'; subject:str; body:str; related_document:str|None=None; send_now:bool=False
class GCConnectIn(BaseModel): company_id:int; institution_id:str; iban_alias:str|None=None; max_historical_days:int=90
class BankSyncIn(BaseModel): date_from:str|None=None; date_to:str|None=None
class AutoEntryFromMovementIn(BaseModel): movement_id:int; tax_rate:float=0.21
class IonosEmailCreateIn(BaseModel): owner_user:str='admin'; domain:str; local_part:str; password:str; display_name:str|None=None

@app.on_event('startup')
def startup(): seed()
@app.get('/')
def root(): return FileResponse(FRONTEND)
@app.get('/api/health')
def health(): return {'status':'ok','version':'1.0.2-test','modules':['accounting','tax','kpi','crm','email','banking-gocardless','bank-dashboard','bank-reconciliation','ionos-provisioning']}

@app.post('/api/managed-clients')
def create_client(item:ManagedClientIn):
    con=db(); cur=con.cursor(); cur.execute('INSERT INTO managed_clients(name,client_type,service_model,created_at) VALUES(?,?,?,?)',(item.name,item.client_type,item.service_model,now())); con.commit(); nid=cur.lastrowid; con.close(); return {'id':nid,**item.dict()}
@app.post('/api/groups')
def create_group(item:GroupIn):
    con=db(); cur=con.cursor(); cur.execute('INSERT INTO groups(managed_client_id,name,group_type,consolidated,created_at) VALUES(?,?,?,?,?)',(item.managed_client_id,item.name,item.group_type,int(item.consolidated),now())); con.commit(); nid=cur.lastrowid; con.close(); return {'id':nid,**item.dict()}
@app.post('/api/companies')
def create_company(item:CompanyIn):
    con=db(); cur=con.cursor(); cur.execute('INSERT INTO companies(managed_client_id,group_id,legal_name,tax_id,country,territory,cnae,consolidation_scope,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(item.managed_client_id,item.group_id,item.legal_name,item.tax_id,item.country,item.territory,item.cnae,item.consolidation_scope,now())); cid=cur.lastrowid
    for acc in DEFAULT_ACCOUNTS: cur.execute('INSERT OR IGNORE INTO accounts(company_id,code,name,account_type,tax_type) VALUES(?,?,?,?,?)',(cid,*acc))
    con.commit(); con.close(); return {'id':cid,**item.dict(),'accounts_created':len(DEFAULT_ACCOUNTS)}
@app.get('/api/companies')
def list_companies(): con=db(); rows=[dict(r) for r in con.execute('SELECT * FROM companies ORDER BY id DESC')]; con.close(); return rows
@app.get('/api/accounts/{company_id}')
def list_accounts(company_id:int): con=db(); rows=[dict(r) for r in con.execute('SELECT code,name,account_type,tax_type FROM accounts WHERE company_id=? ORDER BY code',(company_id,))]; con.close(); return rows
@app.get('/api/search-accounting')
def search_accounting(q:str):
    term=f'%{q.lower()}%'; con=db(); rows=[dict(r) for r in con.execute('''SELECT i.keyword,i.template_code,i.account_code,i.confidence_score,t.name,t.debit_account,t.credit_account,t.tax_account,t.kpi_tag FROM accounting_search_index i JOIN accounting_templates t ON t.code=i.template_code WHERE i.normalized_keyword LIKE ? OR t.keywords LIKE ? ORDER BY i.confidence_score DESC LIMIT 10''',(term,term))]; con.close(); return rows
@app.post('/api/journal-entries')
def create_entry(item:EntryIn):
    debit=sum(l.debit for l in item.lines); credit=sum(l.credit for l in item.lines)
    if round(debit-credit,2)!=0: raise HTTPException(400,f'Asiento descuadrado: debe={debit}, haber={credit}')
    con=db(); cur=con.cursor(); cur.execute('INSERT INTO journal_entries(company_id,entry_date,description,status,source,created_at) VALUES(?,?,?,?,?,?)',(item.company_id,item.entry_date,item.description,'PROPUESTO',item.source,now())); eid=cur.lastrowid
    for l in item.lines: cur.execute('INSERT INTO journal_lines(entry_id,account_code,concept,debit,credit,tax_type,cost_center,third_party) VALUES(?,?,?,?,?,?,?,?)',(eid,l.account_code,l.concept,l.debit,l.credit,l.tax_type,l.cost_center,l.third_party))
    con.commit(); con.close(); return {'id':eid,'status':'PROPUESTO','debit':debit,'credit':credit}
@app.get('/api/journal-entries/{company_id}')
def list_entries(company_id:int):
    con=db(); entries=[]
    for e in con.execute('SELECT * FROM journal_entries WHERE company_id=? ORDER BY entry_date DESC,id DESC',(company_id,)):
        d=dict(e); d['lines']=[dict(r) for r in con.execute('SELECT * FROM journal_lines WHERE entry_id=?',(e['id'],))]; entries.append(d)
    con.close(); return entries

@app.post('/api/crm/contacts')
def create_crm_contact(item:CRMContactIn):
    con=db(); cur=con.cursor(); cur.execute('INSERT INTO crm_contacts(managed_client_id,company_id,contact_type,name,email,phone,notes,created_at) VALUES(?,?,?,?,?,?,?,?)',(item.managed_client_id,item.company_id,item.contact_type,item.name,item.email,item.phone,item.notes,now())); con.commit(); nid=cur.lastrowid; con.close(); return {'id':nid,**item.dict()}
@app.post('/api/email/accounts')
def create_email_account(item:EmailAccountIn):
    con=db(); cur=con.cursor(); cur.execute('INSERT INTO email_accounts(owner_user,display_name,email_address,provider,smtp_host,smtp_port,smtp_user,smtp_password,imap_host,imap_port,use_tls,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(item.owner_user,item.display_name,item.email_address,item.provider,item.smtp_host,item.smtp_port,item.smtp_user,item.smtp_password,item.imap_host,item.imap_port,int(item.use_tls),int(item.active),now())); con.commit(); nid=cur.lastrowid; con.close(); return {'id':nid,'warning':'Prototipo: en producción cifrar credenciales y usar vault.'}
@app.post('/api/crm/messages')
def create_crm_message(item:CRMMessageIn):
    status='PENDIENTE_ENVIO_REAL' if item.send_now else 'BORRADOR'; con=db(); cur=con.cursor(); cur.execute('INSERT INTO crm_messages(managed_client_id,company_id,contact_id,email_account_id,channel,direction,subject,body,status,related_document,created_at,sent_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(item.managed_client_id,item.company_id,item.contact_id,item.email_account_id,item.channel,item.direction,item.subject,item.body,status,item.related_document,now(),None)); con.commit(); nid=cur.lastrowid; con.close(); return {'id':nid,'status':status}

@app.get('/api/banking/providers')
def list_bank_providers(): con=db(); rows=[dict(r) for r in con.execute('SELECT * FROM bank_api_providers ORDER BY name')]; con.close(); return rows
@app.get('/api/banking/gocardless/institutions')
def gc_institutions(country:str='ES'):
    r=requests.get(f'{GC_BASE_URL}/institutions/', params={'country':country}, headers=gc_headers(), timeout=30)
    if r.status_code>=300: raise HTTPException(r.status_code, r.text)
    return r.json()
@app.post('/api/banking/gocardless/connect')
def gc_connect(item:GCConnectIn):
    reference=f'contablos-{item.company_id}-{uuid.uuid4().hex[:12]}'
    payload={'redirect': f'{PUBLIC_BASE_URL}/api/banking/gocardless/callback', 'institution_id': item.institution_id, 'reference': reference, 'agreement': None, 'user_language':'ES'}
    # GoCardless puede requerir agreement para max_historical_days en algunos bancos; dejamos flujo simple compatible.
    r=requests.post(f'{GC_BASE_URL}/requisitions/', json=payload, headers=gc_headers(), timeout=30)
    if r.status_code>=300: raise HTTPException(r.status_code, r.text)
    data=r.json()
    con=db(); cur=con.cursor(); cur.execute('''INSERT INTO bank_connections(company_id,provider_code,bank_institution_id,iban_alias,gocardless_requisition_id,consent_link,consent_status,environment,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',(item.company_id,'GOCARDLESS',item.institution_id,item.iban_alias,data.get('id'),data.get('link'),'CREADO', 'PRODUCTION', now()))
    con.commit(); nid=cur.lastrowid; con.close(); return {'connection_id':nid,'requisition_id':data.get('id'),'consent_link':data.get('link'),'next':'Abrir consent_link para que el cliente autorice su banco'}
@app.get('/api/banking/gocardless/callback')
def gc_callback(ref:str|None=None): return {'status':'ok','message':'Consentimiento recibido. Vuelva a ContabOS y sincronice la conexión.'}
@app.get('/api/banking/connections/{company_id}')
def list_bank_connections(company_id:int): con=db(); rows=[dict(r) for r in con.execute('SELECT * FROM bank_connections WHERE company_id=? ORDER BY id DESC',(company_id,))]; con.close(); return rows
@app.post('/api/banking/connections/{connection_id}/sync')
def sync_connection(connection_id:int,item:BankSyncIn):
    con=db(); cur=con.cursor(); c=cur.execute('SELECT * FROM bank_connections WHERE id=?',(connection_id,)).fetchone()
    if not c: raise HTTPException(404,'Conexión no encontrada')
    date_from=item.date_from or str(date.today().replace(day=1)); date_to=item.date_to or str(date.today())
    movements=[]
    if c['provider_code']=='GOCARDLESS' and c['gocardless_requisition_id']:
        req=requests.get(f'{GC_BASE_URL}/requisitions/{c["gocardless_requisition_id"]}/', headers=gc_headers(), timeout=30)
        if req.status_code>=300: raise HTTPException(req.status_code, req.text)
        reqj=req.json(); accounts=reqj.get('accounts',[])
        cur.execute('UPDATE bank_connections SET account_ids_json=?, consent_status=? WHERE id=?',(json.dumps(accounts),reqj.get('status','UNKNOWN'),connection_id))
        for account_id in accounts:
            tr=requests.get(f'{GC_BASE_URL}/accounts/{account_id}/transactions/', params={'date_from':date_from,'date_to':date_to}, headers=gc_headers(), timeout=30)
            if tr.status_code>=300: continue
            booked=tr.json().get('transactions',{}).get('booked',[])
            for m in booked:
                amt=float(m.get('transactionAmount',{}).get('amount',0))
                concept=m.get('remittanceInformationUnstructured') or m.get('additionalInformation') or m.get('creditorName') or m.get('debtorName') or 'Movimiento bancario'
                sug=suggest_for_text(concept)
                cur.execute('''INSERT INTO bank_movements(company_id,bank_connection_id,account_id,booking_date,value_date,concept,amount,currency,raw_json,suggested_template,suggested_account,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(c['company_id'],connection_id,account_id,m.get('bookingDate'),m.get('valueDate'),concept,amt,m.get('transactionAmount',{}).get('currency','EUR'),json.dumps(m,ensure_ascii=False),sug.get('template_code'),sug.get('account_code'),now()))
                movements.append({'concept':concept,'amount':amt,'suggested_template':sug.get('template_code'),'suggested_account':sug.get('account_code')})
    else:
        demo=[{'date':date_from,'concept':'RECIBO LUZ ENDESA DEMO','amount':-121.0},{'date':date_to,'concept':'TRANSFERENCIA CLIENTE DEMO','amount':500.0}]
        for m in demo:
            sug=suggest_for_text(m['concept']); cur.execute('''INSERT INTO bank_movements(company_id,bank_connection_id,booking_date,concept,amount,currency,raw_json,suggested_template,suggested_account,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',(c['company_id'],connection_id,m['date'],m['concept'],m['amount'],'EUR',json.dumps(m),sug.get('template_code'),sug.get('account_code'),now())); movements.append({**m,'suggested_template':sug.get('template_code'),'suggested_account':sug.get('account_code')})
    cur.execute('INSERT INTO bank_import_jobs(bank_connection_id,date_from,date_to,status,result_json,created_at) VALUES(?,?,?,?,?,?)',(connection_id,date_from,date_to,'COMPLETADO',json.dumps(movements,ensure_ascii=False),now()))
    cur.execute('UPDATE bank_connections SET last_sync_at=? WHERE id=?',(now(),connection_id)); con.commit(); jid=cur.lastrowid; con.close(); return {'job_id':jid,'imported':len(movements),'movements':movements}
@app.get('/api/banking/movements/{company_id}')
def list_movements(company_id:int,status:str|None=None):
    con=db(); q='SELECT * FROM bank_movements WHERE company_id=?'; params=[company_id]
    if status: q+=' AND reconciliation_status=?'; params.append(status)
    rows=[dict(r) for r in con.execute(q+' ORDER BY booking_date DESC,id DESC',params)]; con.close(); return rows
@app.post('/api/banking/reconcile/auto-entry')
def auto_entry_from_movement(item:AutoEntryFromMovementIn):
    con=db(); cur=con.cursor(); m=cur.execute('SELECT * FROM bank_movements WHERE id=?',(item.movement_id,)).fetchone()
    if not m: raise HTTPException(404,'Movimiento no encontrado')
    if m['journal_entry_id']: return {'journal_entry_id':m['journal_entry_id'],'status':'YA_CONTABILIZADO'}
    amount=abs(float(m['amount'])); sug=suggest_for_text(m['concept']); template=sug.get('template_code')
    if float(m['amount']) < 0:
        base=round(amount/(1+item.tax_rate),2) if template and template.startswith('GASTO_') else amount
        tax=round(amount-base,2) if base!=amount else 0
        lines=[('628' if template=='GASTO_LUZ' else (sug.get('account_code') or '629'), m['concept'], base,0,None),]
        if tax: lines.append(('472000','IVA/IGIC soportado estimado',tax,0,'IVA_SOPORTADO'))
        lines.append(('572','Pago banco',0,amount,None))
    else:
        lines=[('572','Cobro banco',amount,0,None),('430',m['concept'],0,amount,None)]
    cur.execute('INSERT INTO journal_entries(company_id,entry_date,description,status,source,created_at) VALUES(?,?,?,?,?,?)',(m['company_id'],m['booking_date'] or str(date.today()),'Auto-asiento desde banco: '+m['concept'],'PROPUESTO','BANK_AUTO',now())); eid=cur.lastrowid
    for a,cpt,d,h,tax in lines: cur.execute('INSERT INTO journal_lines(entry_id,account_code,concept,debit,credit,tax_type) VALUES(?,?,?,?,?,?)',(eid,a,cpt,d,h,tax))
    cur.execute('UPDATE bank_movements SET reconciliation_status=?, journal_entry_id=? WHERE id=?',('PROPUESTA_ASIENTO',eid,item.movement_id)); con.commit(); con.close(); return {'journal_entry_id':eid,'status':'PROPUESTA_ASIENTO','lines':lines}
@app.get('/api/banking/dashboard/{company_id}')
def bank_dashboard(company_id:int):
    con=db(); rows=[dict(r) for r in con.execute('SELECT * FROM bank_movements WHERE company_id=?',(company_id,))]
    total=sum(float(r['amount']) for r in rows); pending=sum(1 for r in rows if r['reconciliation_status']=='PENDIENTE'); payments=sum(float(r['amount']) for r in rows if float(r['amount'])<0); receipts=sum(float(r['amount']) for r in rows if float(r['amount'])>0)
    by_template={}
    for r in rows: by_template[r['suggested_template'] or 'SIN_CLASIFICAR']=by_template.get(r['suggested_template'] or 'SIN_CLASIFICAR',0)+1
    con.close(); return {'company_id':company_id,'movements':len(rows),'pending_reconciliation':pending,'net_cash_flow':round(total,2),'payments':round(payments,2),'receipts':round(receipts,2),'by_template':by_template}

@app.post('/api/ionos/email-accounts')
def ionos_create_email(item:IonosEmailCreateIn):
    email=f'{item.local_part}@{item.domain}'.lower()
    # IONOS publica API de hosting/dominios/DNS/SSL. La creación de buzones depende del producto y puede no estar expuesta en todas las cuentas.
    payload={'email':email,'password':item.password,'displayName':item.display_name or item.local_part}
    provider_response={'mode':'LOCAL_REGISTERED','note':'Preparado para API IONOS. Si el contrato expone endpoint de mailboxes, configure IONOS_API_BASE/IONOS_API_KEY y adapte ruta en services/ionos_mail_provider.py.'}
    if IONOS_API_KEY and os.getenv('IONOS_MAILBOX_ENDPOINT'):
        endpoint=os.getenv('IONOS_MAILBOX_ENDPOINT')
        r=requests.post(endpoint, json=payload, headers={'Authorization': f'Bearer {IONOS_API_KEY}','Content-Type':'application/json'}, timeout=30)
        provider_response={'status_code':r.status_code,'text':r.text[:1000]}
        if r.status_code>=300: raise HTTPException(r.status_code, r.text)
    con=db(); cur=con.cursor(); cur.execute('INSERT INTO ionos_accounts(owner_user,domain,local_part,email_address,password_hash,display_name,provider_response,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(item.owner_user,item.domain,item.local_part,email,hash_secret(item.password),item.display_name,json.dumps(provider_response,ensure_ascii=False),'CREADO_LOCAL' if not os.getenv('IONOS_MAILBOX_ENDPOINT') else 'CREADO_API',now()))
    cur.execute('INSERT INTO email_accounts(owner_user,display_name,email_address,provider,smtp_host,smtp_port,smtp_user,smtp_password,imap_host,imap_port,use_tls,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(item.owner_user,item.display_name or item.local_part,email,'IONOS','smtp.ionos.es',587,email,item.password,'imap.ionos.es',993,1,1,now()))
    con.commit(); nid=cur.lastrowid; con.close(); return {'id':nid,'email_address':email,'provider_response':provider_response,'smtp':'smtp.ionos.es:587','imap':'imap.ionos.es:993'}
@app.get('/api/ionos/email-accounts')
def ionos_list(): con=db(); rows=[dict(r) for r in con.execute('SELECT id,owner_user,domain,local_part,email_address,display_name,status,created_at FROM ionos_accounts ORDER BY id DESC')]; con.close(); return rows
