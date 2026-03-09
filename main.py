from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, event, or_, UniqueConstraint, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "gestionale.db"
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.close()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)  # LASER | MANIPOLO
    serial = Column(String, unique=True, nullable=False)
    status = Column(String, default="ATTIVO")
    location = Column(String, default="")
    region = Column(String, default="")
    note = Column(Text, default="")
    created_at = Column(String, default=now_iso)
    events = relationship("Event", back_populates="item", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    event_date = Column(String, default=now_iso)
    event_type = Column(String, nullable=False)
    from_location = Column(String, default="")
    to_location = Column(String, default="")
    note = Column(Text, default="")
    item = relationship("Item", back_populates="events")


class Center(Base):
    __tablename__ = "centers"
    id = Column(Integer, primary_key=True)
    region = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("region", "name", name="uq_centers_region_name"),
    )


class HiddenCenter(Base):
    __tablename__ = "hidden_centers"
    id = Column(Integer, primary_key=True)
    region = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("region", "name", name="uq_hidden_centers_region_name"),
    )


Base.metadata.create_all(engine)

with engine.begin() as conn:
    cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(items)").fetchall()]
    if "region" not in cols:
        conn.exec_driver_sql("ALTER TABLE items ADD COLUMN region VARCHAR DEFAULT ''")

    conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS centers (
            id INTEGER PRIMARY KEY,
            region VARCHAR NOT NULL,
            name VARCHAR NOT NULL
        )
    """)
    conn.exec_driver_sql("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_centers_region_name
        ON centers(region, name)
    """)

    conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS hidden_centers (
            id INTEGER PRIMARY KEY,
            region VARCHAR NOT NULL,
            name VARCHAR NOT NULL
        )
    """)
    conn.exec_driver_sql("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hidden_centers_region_name
        ON hidden_centers(region, name)
    """)

app = FastAPI(title="Gestionale Laser EPIL POINT", version="1.0")


class ItemIn(BaseModel):
    type: str = Field(pattern="^(LASER|MANIPOLO)$")
    serial: str = Field(min_length=1, max_length=120)
    status: str = "ATTIVO"
    location: str = ""
    region: str = ""
    note: str = ""


class EventIn(BaseModel):
    event_type: str = Field(min_length=1, max_length=120)
    from_location: str = ""
    to_location: str = ""
    note: str = ""


class CenterIn(BaseModel):
    region: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)


REGIONS = [
    "CAMPANIA",
    "LAZIO",
    "TOSCANA",
    "PUGLIA",
    "SICILIA",
    "ABRUZZO",
    "EMILIA ROMAGNA",
    "LOMBARDIA",
    "PIEMONTE",
    "SEDE",
]


def clean_region(value: str | None) -> str:
    return (value or "").strip().upper()


def clean_center(value: str | None) -> str:
    return (value or "").strip()


def clean_serial(value: str | None) -> str:
    return (value or "").strip().upper()


def item_to_dict(i: Item):
    return {
        "id": i.id,
        "type": i.type,
        "serial": i.serial,
        "status": i.status or "",
        "location": i.location or "",
        "region": i.region or "",
        "note": i.note or "",
        "created_at": i.created_at or "",
        "events_count": len(i.events),
    }


CSS = r'''
:root{
  --bg:#fbfaf6;
  --paper:#ffffff;
  --paper-2:#fffdfa;
  --text:#2e2417;
  --muted:#7d6a52;
  --line:rgba(140,114,73,.18);
  --gold:#c7a46a;
  --gold-strong:#b88d4b;
  --gold-soft:#efe2cb;
  --green:#1f9d55;
  --green-bg:#e9f8ef;
  --red:#d83b3b;
  --red-bg:#fff0f0;
  --shadow:0 14px 34px rgba(87,65,35,.10);
  --shadow-soft:0 8px 20px rgba(87,65,35,.08);
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
  color:var(--text);
  background:
    radial-gradient(900px 500px at 10% 0%, rgba(199,164,106,.12), transparent 60%),
    radial-gradient(900px 500px at 100% 10%, rgba(199,164,106,.10), transparent 60%),
    var(--bg);
}
.hidden{display:none !important}
.topbar{
  position:sticky;top:0;z-index:50;
  backdrop-filter:blur(10px);
  background:rgba(255,255,255,.86);
  border-bottom:1px solid var(--line);
}
.topbar-inner{
  max-width:1240px;margin:0 auto;padding:16px 22px;
  display:flex;align-items:center;justify-content:space-between;gap:12px;
}
.brand{display:flex;align-items:center;gap:14px;min-width:0}
.logo{
  width:46px;height:46px;border-radius:14px;display:grid;place-items:center;
  background:linear-gradient(135deg,var(--gold),var(--gold-strong));
  color:#fff;font-weight:900;box-shadow:var(--shadow-soft);flex:0 0 auto;
}
.brand-title{font-weight:900;letter-spacing:.02em}
.brand-sub{font-size:13px;color:var(--muted);margin-top:2px}
.container{max-width:1240px;margin:0 auto;padding:28px 22px 48px}
.hero{
  background:linear-gradient(180deg, rgba(255,255,255,.95), rgba(255,251,244,.92));
  border:1px solid var(--line);
  border-radius:30px;
  box-shadow:var(--shadow);
  overflow:hidden;
}
.hero-inner{padding:34px 28px 30px;text-align:center}
.eyebrow{
  display:inline-flex;align-items:center;gap:8px;
  font-size:12px;font-weight:900;letter-spacing:.18em;text-transform:uppercase;
  color:var(--gold-strong);margin-bottom:10px;
}
h1{margin:0;font-size:42px;letter-spacing:-.04em}
.lead{max-width:760px;margin:14px auto 0;color:var(--muted);line-height:1.65}
.grid-regions{
  display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:30px;
}
.region-card, .center-card, .summary-card, .item-card, .events-panel, .filters-box, .editor-box, .modal-card{
  background:var(--paper);
  border:1px solid var(--line);
  box-shadow:var(--shadow-soft);
}
.region-card{
  border-radius:24px;padding:22px;cursor:pointer;text-align:left;
  transition:transform .14s ease, border-color .14s ease, box-shadow .14s ease;
}
.region-card:hover,.center-card:hover,.item-card:hover{
  transform:translateY(-3px);
  border-color:rgba(184,141,75,.38);
  box-shadow:0 16px 34px rgba(87,65,35,.14);
}
.region-title{font-size:22px;font-weight:900;letter-spacing:-.03em}
.region-desc{margin-top:8px;color:var(--muted);line-height:1.55;font-size:14px}
.toolbar{
  display:flex;align-items:flex-end;justify-content:space-between;
  gap:14px;margin-bottom:16px;flex-wrap:wrap
}
.toolbar h2{margin:0;font-size:30px;letter-spacing:-.03em}
.muted{color:var(--muted);font-size:14px}
.row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.btn{
  border:1px solid var(--line);background:var(--paper);color:var(--text);cursor:pointer;
  border-radius:14px;padding:11px 14px;font-weight:800;
  transition:transform .08s ease,border-color .12s ease,background .12s ease;
  min-height:44px;
}
.btn:hover{transform:translateY(-1px);border-color:rgba(184,141,75,.42)}
.btn.primary{
  background:linear-gradient(180deg,var(--gold),var(--gold-strong));
  color:#fff;border-color:transparent;
}
.btn.ghost{background:transparent}
.btn.danger{background:linear-gradient(180deg,#ef5a5a,#d83b3b);color:#fff;border-color:transparent}
.input, select.input, textarea.input{
  width:100%;border:1px solid var(--line);background:#fff;border-radius:14px;
  padding:12px 13px;outline:none;color:var(--text);min-height:46px;
  font-size:16px;
}
.input:focus, select.input:focus, textarea.input:focus{
  border-color:rgba(184,141,75,.55);
  box-shadow:0 0 0 4px rgba(199,164,106,.16);
}
.filters-box{border-radius:22px;padding:18px;margin-bottom:18px}
.filters-grid{display:grid;grid-template-columns:1.2fr .9fr .9fr auto;gap:12px;align-items:end}
.centers-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.center-card{border-radius:22px;padding:22px;cursor:pointer}
.center-name{font-size:22px;font-weight:900;letter-spacing:-.02em}
.center-meta{margin-top:10px;color:var(--muted);font-size:14px;line-height:1.55}
.summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}
.summary-card{border-radius:22px;padding:18px}
.summary-label{font-size:12px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);font-weight:800}
.summary-value{
  font-size:30px;font-weight:900;margin-top:8px;
  overflow-wrap:anywhere;
}
.two-col{display:grid;grid-template-columns:1.15fr .9fr;gap:18px;align-items:start}
.section-box{margin-bottom:18px}
.section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
.section-head h3{margin:0;font-size:22px}
.items-grid{display:grid;grid-template-columns:1fr;gap:12px}
.item-card{border-radius:20px;padding:16px}
.item-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.item-serial{
  font-size:22px;font-weight:900;letter-spacing:-.02em;
  overflow-wrap:anywhere;
}
.item-type{font-size:12px;font-weight:900;letter-spacing:.14em;color:var(--muted);text-transform:uppercase;margin-bottom:6px}
.item-note{margin-top:10px;color:var(--muted);line-height:1.55;font-size:14px;overflow-wrap:anywhere}
.item-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.status-pill{
  display:inline-flex;align-items:center;justify-content:center;
  border-radius:999px;padding:8px 12px;font-size:12px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;
}
.status-attivo{background:var(--green-bg);color:var(--green);border:1px solid rgba(31,157,85,.22)}
.status-non-attivo{background:var(--red-bg);color:var(--red);border:1px solid rgba(216,59,59,.22)}
.status-other{background:#f6f2eb;color:#8a6a3c;border:1px solid rgba(184,141,75,.18)}
.events-panel{border-radius:22px;padding:18px}
.event-list{display:flex;flex-direction:column;gap:12px}
.event-card{border:1px solid var(--line);border-radius:18px;padding:14px;background:var(--paper-2)}
.event-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.event-title{font-weight:900;overflow-wrap:anywhere}
.event-meta{margin-top:8px;color:var(--muted);font-size:14px;line-height:1.55;overflow-wrap:anywhere}
.event-badge{
  font-size:12px;border-radius:999px;padding:5px 10px;background:#f5ede0;color:#8a6a3c;
  font-weight:800;white-space:nowrap
}
.editor-box{border-radius:22px;padding:18px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
label{display:flex;flex-direction:column;gap:7px;font-size:13px;color:var(--muted)}
textarea.input{resize:vertical;min-height:96px}
.modal{
  position:fixed;inset:0;z-index:999;background:rgba(43,31,13,.30);
  display:grid;place-items:center;padding:18px
}
.modal-card{
  width:min(760px,96vw);max-height:92vh;overflow:auto;
  border-radius:24px;padding:18px;
  -webkit-overflow-scrolling:touch;
}
.modal-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:14px}
.icon-btn{
  width:42px;height:42px;border-radius:12px;border:1px solid var(--line);
  background:#fff;cursor:pointer;flex:0 0 auto
}
.icon-btn:hover{border-color:rgba(184,141,75,.40)}
.sep{border:0;border-top:1px solid var(--line);margin:16px 0}
.toast{
  position:fixed;right:16px;bottom:16px;z-index:1000;
  background:#2e2417;color:#fff;padding:11px 14px;border-radius:14px;
  box-shadow:0 18px 44px rgba(43,31,13,.24);
  max-width:min(90vw,360px);
}
.empty{
  border:1px dashed rgba(184,141,75,.35);border-radius:18px;
  padding:18px;color:var(--muted);background:#fffdfa;
}

@media (max-width:1100px){
  .grid-regions{grid-template-columns:repeat(2,1fr)}
  .centers-grid{grid-template-columns:repeat(2,1fr)}
  .summary-grid{grid-template-columns:repeat(2,1fr)}
  .two-col{grid-template-columns:1fr}
}

@media (max-width:760px){
  body{background:var(--bg)}
  .container{padding:16px 12px 28px}
  .topbar-inner{padding:12px}
  .brand-title{font-size:15px}
  .brand-sub{font-size:11px}
  .hero{border-radius:22px}
  .hero-inner{padding:24px 16px}
  h1{font-size:30px;line-height:1.08}
  .lead{font-size:14px}
  .grid-regions,.centers-grid,.summary-grid,.form-grid,.filters-grid,.two-col{grid-template-columns:1fr}
  .toolbar{align-items:stretch}
  .toolbar > div{width:100%}
  .toolbar .row{width:100%}
  .toolbar .row .btn{flex:1 1 100%;width:100%}
  .section-head{flex-direction:column;align-items:flex-start}
  .section-head h3{font-size:20px}
  .item-top,.event-top,.modal-head{flex-direction:column;align-items:flex-start}
  .status-pill,.event-badge{white-space:normal}
  .summary-value{font-size:24px}
  .region-card,.center-card,.summary-card,.item-card,.events-panel,.filters-box,.editor-box,.modal-card{border-radius:18px}
  .item-actions .btn{flex:1 1 100%;width:100%}
  .row{align-items:stretch}
  .row .btn{width:100%}
  .modal{padding:10px}
  .modal-card{width:100%;max-height:94vh;padding:14px;border-radius:18px}
}

@media (max-width:420px){
  .logo{width:40px;height:40px;border-radius:12px}
  h1{font-size:26px}
  .region-title,.center-name{font-size:20px}
  .item-serial{font-size:20px}
  .summary-value{font-size:22px}
}
'''

JS = r'''
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let currentRegion = null;
let currentCenter = null;
let currentItemId = null;
let pendingDeleteId = null;
let itemModalMode = "new";

function toast(msg){
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=> t.remove(), 2200);
}

function escapeHtml(value){
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function statusClass(status){
  const s = (status || "").trim().toUpperCase();
  if(s === "ATTIVO") return "status-pill status-attivo";
  if(s === "NON ATTIVO") return "status-pill status-non-attivo";
  return "status-pill status-other";
}

function prettyDate(iso){
  return (iso || "").replace("T", " ");
}

async function api(path, opts={}){
  const res = await fetch(path, {
    headers: {"Content-Type":"application/json"},
    ...opts,
  });

  if(!res.ok){
    let msg = "Errore";
    try{
      const data = await res.json();
      msg = data.detail || msg;
    }catch(_){}
    throw new Error(msg);
  }

  if(res.status === 204) return null;
  return res.json();
}

function showView(id){
  closeItemModal();
  closeDeleteModal();
  closeAddCenterModal();
  closeRemoveCenterModal();
  $$(".view").forEach(v => v.classList.add("hidden"));
  $(id).classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function goHome(){
  currentRegion = null;
  currentCenter = null;
  currentItemId = null;
  showView("#viewHome");
}

async function loadRegions(){
  const data = await api("/api/regions");
  const wrap = $("#regionsGrid");
  wrap.innerHTML = "";

  for(const region of data){
    const card = document.createElement("button");
    card.className = "region-card";
    card.innerHTML = `
      <div class="region-title">${escapeHtml(region.name)}</div>
      <div class="region-desc">Apri i centri della regione e consulta laser, manipoli, stati ed eventi.</div>
    `;
    card.addEventListener("click", ()=> goRegion(region.name));
    wrap.appendChild(card);
  }
}

async function goRegion(region){
  currentRegion = region;
  currentCenter = null;
  $("#regionTitle").textContent = region;
  $("#regionSub").textContent = "Seleziona un centro per vedere laser, manipoli e storico eventi.";
  showView("#viewRegion");
  await loadCenters();
}

async function loadCenters(){
  const wrap = $("#centersGrid");
  wrap.innerHTML = `<div class="empty">Caricamento centri...</div>`;

  const centers = await api(`/api/centers?region=${encodeURIComponent(currentRegion)}`);
  const q = $("#centerSearch").value.trim().toLowerCase();
  const filtered = centers.filter(c => c.name.toLowerCase().includes(q));

  if(filtered.length === 0){
    wrap.innerHTML = `<div class="empty">Nessun centro trovato in questa regione.</div>`;
    return;
  }

  wrap.innerHTML = "";
  for(const center of filtered){
    const card = document.createElement("button");
    card.className = "center-card";
    card.innerHTML = `
      <div class="center-name">${escapeHtml(center.name)}</div>
      <div class="center-meta">Visualizza i seriali presenti nel centro, lo stato dei dispositivi e lo storico aggiornamenti.</div>
    `;
    card.addEventListener("click", ()=> goCenter(center.name));
    wrap.appendChild(card);
  }
}

async function goCenter(center){
  currentCenter = center;
  $("#centerTitle").textContent = center;
  $("#centerSub").textContent = `${currentRegion} · panoramica completa del centro`;
  showView("#viewCenter");
  await loadCenterDetail();
}

async function loadCenterDetail(){
  const data = await api(`/api/centers/${encodeURIComponent(currentRegion)}/${encodeURIComponent(currentCenter)}`);

  $("#sumRegion").textContent = data.region;
  $("#sumCenter").textContent = data.center;
  $("#sumLaser").textContent = data.counts.laser;
  $("#sumManipoli").textContent = data.counts.manipoli;

  renderItems("#laserList", data.lasers, "LASER");
  renderItems("#manipoliList", data.manipoli, "MANIPOLO");
  renderEvents(data.events);
}

function renderItems(target, items, type){
  const wrap = $(target);
  wrap.innerHTML = "";

  if(items.length === 0){
    wrap.innerHTML = `<div class="empty">Nessun ${type === "LASER" ? "laser" : "manipolo"} presente.</div>`;
    return;
  }

  for(const item of items){
    const div = document.createElement("div");
    div.className = "item-card";
    div.innerHTML = `
      <div class="item-top">
        <div>
          <div class="item-type">${escapeHtml(item.type)}</div>
          <div class="item-serial">${escapeHtml(item.serial)}</div>
        </div>
        <div class="${statusClass(item.status)}">${escapeHtml(item.status || "-")}</div>
      </div>
      <div class="item-note">Centro: <strong>${escapeHtml(item.location || "-")}</strong> · Regione: <strong>${escapeHtml(item.region || "-")}</strong> · Eventi: <strong>${item.events_count}</strong></div>
      ${item.note ? `<div class="item-note">${escapeHtml(item.note)}</div>` : ""}
      <div class="item-actions">
        <button class="btn" onclick="openEditItem(${item.id})">Apri / Modifica</button>
        <button class="btn danger" onclick="openDeleteModal(${item.id}, '${escapeHtml(item.serial)}')">Rimuovi</button>
      </div>
    `;
    wrap.appendChild(div);
  }
}

function renderEvents(events){
  const wrap = $("#eventsList");
  wrap.innerHTML = "";

  if(events.length === 0){
    wrap.innerHTML = `<div class="empty">Nessun evento registrato per questo centro.</div>`;
    return;
  }

  for(const ev of events){
    const move = (ev.from_location || ev.to_location)
      ? `${escapeHtml(ev.from_location || "-")} → ${escapeHtml(ev.to_location || "-")}`
      : "Nessuno spostamento indicato";

    const div = document.createElement("div");
    div.className = "event-card";
    div.innerHTML = `
      <div class="event-top">
        <div>
          <div class="event-title">${escapeHtml(ev.event_type)}</div>
          <div class="event-meta">${escapeHtml(ev.item_type)} · <strong>${escapeHtml(ev.serial)}</strong></div>
        </div>
        <div class="event-badge">${prettyDate(ev.event_date)}</div>
      </div>
      <div class="event-meta">${move}</div>
      ${ev.note ? `<div class="event-meta">${escapeHtml(ev.note)}</div>` : ""}
    `;
    wrap.appendChild(div);
  }
}

function resetItemModal(){
  $("#itemMsg").textContent = "";
  $("#iType").value = "LASER";
  $("#iSerial").value = "";
  $("#iStatus").value = "ATTIVO";
  $("#iLocation").value = currentCenter || "";
  $("#iRegion").value = currentRegion || "";
  $("#iNote").value = "";
  $("#eventForm").classList.add("hidden");
  $("#eType").value = "";
  $("#eFrom").value = currentCenter || "";
  $("#eTo").value = currentCenter || "";
  $("#eNote").value = "";
  $("#eventMsg").textContent = "";
  $("#singleEvents").innerHTML = `<div class="empty">Apri un elemento esistente per vedere il suo storico eventi.</div>`;
}

function openNewItem(type){
  itemModalMode = "new";
  currentItemId = null;
  resetItemModal();
  $("#iType").value = type || "LASER";
  $("#itemModalTitle").textContent = "Nuovo elemento";
  $("#btnDeleteItemFromModal").classList.add("hidden");
  $("#btnShowEventForm").classList.add("hidden");
  $("#itemModal").classList.remove("hidden");
}

async function openEditItem(itemId){
  itemModalMode = "edit";
  currentItemId = itemId;
  resetItemModal();
  const item = await api(`/api/items/${itemId}`);

  $("#itemModalTitle").textContent = `${item.type} · ${item.serial}`;
  $("#iType").value = item.type;
  $("#iSerial").value = item.serial || "";
  $("#iStatus").value = item.status || "";
  $("#iLocation").value = item.location || "";
  $("#iRegion").value = item.region || "";
  $("#iNote").value = item.note || "";
  $("#btnDeleteItemFromModal").classList.remove("hidden");
  $("#btnShowEventForm").classList.remove("hidden");
  $("#itemModal").classList.remove("hidden");
  renderSingleItemEvents(item.events || []);
}

function renderSingleItemEvents(events){
  const wrap = $("#singleEvents");
  wrap.innerHTML = "";

  if(events.length === 0){
    wrap.innerHTML = `<div class="empty">Nessun evento ancora registrato.</div>`;
    return;
  }

  for(const ev of events){
    const move = (ev.from_location || ev.to_location)
      ? `${escapeHtml(ev.from_location || "-")} → ${escapeHtml(ev.to_location || "-")}`
      : "Nessuno spostamento indicato";

    const div = document.createElement("div");
    div.className = "event-card";
    div.innerHTML = `
      <div class="event-top">
        <div class="event-title">${escapeHtml(ev.event_type)}</div>
        <div class="event-badge">${prettyDate(ev.event_date)}</div>
      </div>
      <div class="event-meta">${move}</div>
      ${ev.note ? `<div class="event-meta">${escapeHtml(ev.note)}</div>` : ""}
    `;
    wrap.appendChild(div);
  }
}

function closeItemModal(){
  $("#itemModal").classList.add("hidden");
}

function openDeleteModal(id, serial){
  pendingDeleteId = id;
  $("#deleteSerialName").textContent = serial || "questo elemento";
  $("#deleteModal").classList.remove("hidden");
}

function closeDeleteModal(){
  pendingDeleteId = null;
  $("#deleteModal").classList.add("hidden");
}

function openAddCenterModal(){
  $("#newCenterName").value = "";
  $("#centerAddMsg").textContent = "";
  $("#centerAddModal").classList.remove("hidden");
}

function closeAddCenterModal(){
  const el = $("#centerAddModal");
  if(el) el.classList.add("hidden");
}

async function openRemoveCenterModal(){
  $("#centerRemoveMsg").textContent = "";
  const select = $("#removeCenterSelect");
  select.innerHTML = `<option value="">Caricamento...</option>`;
  $("#centerRemoveModal").classList.remove("hidden");

  try{
    const centers = await api(`/api/centers/manage/list?region=${encodeURIComponent(currentRegion)}`);
    if(!centers.length){
      select.innerHTML = `<option value="">Nessun centro disponibile</option>`;
      return;
    }

    select.innerHTML = `<option value="">Seleziona un centro</option>`;
    for(const c of centers){
      const opt = document.createElement("option");
      opt.value = c.name;
      opt.textContent = c.name;
      select.appendChild(opt);
    }
  }catch(err){
    select.innerHTML = `<option value="">Errore caricamento</option>`;
    $("#centerRemoveMsg").textContent = err.message;
  }
}

function closeRemoveCenterModal(){
  const el = $("#centerRemoveModal");
  if(el) el.classList.add("hidden");
}

async function saveCenter(){
  const name = $("#newCenterName").value.trim();
  if(!name){
    $("#centerAddMsg").textContent = "Inserisci il nome del centro.";
    return;
  }

  try{
    await api("/api/centers", {
      method: "POST",
      body: JSON.stringify({
        region: currentRegion,
        name: name
      })
    });

    closeAddCenterModal();
    toast("Centro aggiunto ✅");
    await loadCenters();
  }catch(err){
    $("#centerAddMsg").textContent = err.message;
  }
}

async function removeCenter(){
  const name = $("#removeCenterSelect").value.trim();
  if(!name){
    $("#centerRemoveMsg").textContent = "Seleziona un centro.";
    return;
  }

  try{
    await api(`/api/centers/${encodeURIComponent(currentRegion)}/${encodeURIComponent(name)}`, {
      method: "DELETE"
    });

    closeRemoveCenterModal();
    toast("Centro rimosso ✅");
    await loadCenters();

    if(currentCenter === name){
      currentCenter = null;
      await goRegion(currentRegion);
    }
  }catch(err){
    $("#centerRemoveMsg").textContent = err.message;
  }
}

async function saveItem(){
  const payload = {
    type: $("#iType").value,
    serial: $("#iSerial").value.trim().toUpperCase(),
    status: $("#iStatus").value.trim() || "ATTIVO",
    location: $("#iLocation").value.trim(),
    region: $("#iRegion").value.trim().toUpperCase(),
    note: $("#iNote").value.trim(),
  };

  if(!payload.serial){
    $("#itemMsg").textContent = "Inserisci il codice seriale.";
    return;
  }

  if(!payload.region){
    $("#itemMsg").textContent = "Inserisci la regione.";
    return;
  }

  if(!payload.location){
    $("#itemMsg").textContent = "Inserisci il centro/città.";
    return;
  }

  try{
    if(itemModalMode === "new"){
      await api("/api/items", { method:"POST", body: JSON.stringify(payload) });
      toast("Elemento aggiunto ✅");
    } else {
      await api(`/api/items/${currentItemId}`, { method:"PATCH", body: JSON.stringify(payload) });
      toast("Elemento aggiornato ✅");
    }

    closeItemModal();
    await loadCenterDetail();
  }catch(err){
    $("#itemMsg").textContent = err.message;
  }
}

async function saveEvent(){
  const payload = {
    event_type: $("#eType").value.trim(),
    from_location: $("#eFrom").value.trim(),
    to_location: $("#eTo").value.trim(),
    note: $("#eNote").value.trim(),
  };

  if(!payload.event_type){
    $("#eventMsg").textContent = "Inserisci il tipo evento.";
    return;
  }

  try{
    await api(`/api/items/${currentItemId}/events`, { method:"POST", body: JSON.stringify(payload) });
    $("#eventMsg").textContent = "Evento registrato";
    toast("Evento aggiunto ✅");
    const item = await api(`/api/items/${currentItemId}`);
    renderSingleItemEvents(item.events || []);
    await loadCenterDetail();
  }catch(err){
    $("#eventMsg").textContent = err.message;
  }
}

document.addEventListener("DOMContentLoaded", async ()=>{
  await loadRegions();
  showView("#viewHome");

  $("#btnHome").addEventListener("click", goHome);
  $("#btnBackToRegions").addEventListener("click", goHome);
  $("#btnBackToCenters").addEventListener("click", ()=> goRegion(currentRegion));

  $("#btnAddCenter").addEventListener("click", openAddCenterModal);
  $("#btnRemoveCenter").addEventListener("click", ()=> openRemoveCenterModal().catch(()=>{}));

  $("#centerAddModalClose").addEventListener("click", closeAddCenterModal);
  $("#centerAddModal").addEventListener("click", (e)=>{ if(e.target.id === "centerAddModal") closeAddCenterModal(); });
  $("#centerAddConfirm").addEventListener("click", saveCenter);

  $("#centerRemoveModalClose").addEventListener("click", closeRemoveCenterModal);
  $("#centerRemoveModal").addEventListener("click", (e)=>{ if(e.target.id === "centerRemoveModal") closeRemoveCenterModal(); });
  $("#centerRemoveConfirm").addEventListener("click", removeCenter);

  $("#centerSearch").addEventListener("input", ()=> loadCenters().catch(()=>{}));

  $("#btnNewLaser").addEventListener("click", ()=> openNewItem("LASER"));
  $("#btnNewManipolo").addEventListener("click", ()=> openNewItem("MANIPOLO"));

  $("#itemModalClose").addEventListener("click", closeItemModal);
  $("#itemModal").addEventListener("click", (e)=>{ if(e.target.id === "itemModal") closeItemModal(); });
  $("#btnSaveItem").addEventListener("click", saveItem);
  $("#btnShowEventForm").addEventListener("click", ()=> $("#eventForm").classList.toggle("hidden"));
  $("#btnSaveEvent").addEventListener("click", saveEvent);
  $("#btnDeleteItemFromModal").addEventListener("click", ()=>{
    if(currentItemId){
      openDeleteModal(currentItemId, $("#iSerial").value.trim());
    }
  });

  $("#deleteModalClose").addEventListener("click", closeDeleteModal);
  $("#deleteCancel").addEventListener("click", closeDeleteModal);
  $("#deleteModal").addEventListener("click", (e)=>{ if(e.target.id === "deleteModal") closeDeleteModal(); });
  $("#deleteConfirm").addEventListener("click", async ()=>{
    if(!pendingDeleteId) return;
    await api(`/api/items/${pendingDeleteId}`, { method:"DELETE" });
    closeDeleteModal();
    closeItemModal();
    toast("Elemento rimosso ✅");
    await loadCenterDetail();
  });

  document.addEventListener("keydown", (e)=>{
    if(e.key === "Escape"){
      closeItemModal();
      closeDeleteModal();
      closeAddCenterModal();
      closeRemoveCenterModal();
    }
  });
});
'''

HTML = f'''<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Gestionale Laser EPIL POINT</title>
  <link rel="stylesheet" href="/style.css?v=12" />
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand">
        <div class="logo">EP</div>
        <div>
          <div class="brand-title">Gestionale Laser EPIL POINT</div>
          <div class="brand-sub">Created by Tony Esposito</div>
        </div>
      </div>
      <div class="row">
        <button class="btn ghost" id="btnHome">Home</button>
      </div>
    </div>
  </header>

  <main class="container">
    <section id="viewHome" class="view">
      <div class="hero">
        <div class="hero-inner">
          <div class="eyebrow">EPIL POINT · LASER ASSET</div>
          <h1>Seleziona una regione</h1>
          <p class="lead">
            TEAM LASER: ANTONIO U.T - TONY ESPOSITO - FRANCESCO DE MARTINO.
          </p>
          <div class="grid-regions" id="regionsGrid"></div>
        </div>
      </div>
    </section>

    <section id="viewRegion" class="view hidden">
      <div class="toolbar">
        <div>
          <h2 id="regionTitle">Regione</h2>
          <div class="muted" id="regionSub"></div>
        </div>
        <div class="row">
          <button class="btn ghost" id="btnBackToRegions">← Regioni</button>
          <button class="btn primary" id="btnAddCenter">+ Aggiungi centro</button>
          <button class="btn danger" id="btnRemoveCenter">Rimuovi centro</button>
        </div>
      </div>

      <div class="filters-box">
        <div class="filters-grid">
          <label>
            Cerca centro
            <input id="centerSearch" class="input" placeholder="Es. Vomero, Cassino, Bari..." />
          </label>
          <div></div>
          <div></div>
          <div></div>
        </div>
      </div>

      <div class="centers-grid" id="centersGrid"></div>
    </section>

    <section id="viewCenter" class="view hidden">
      <div class="toolbar">
        <div>
          <h2 id="centerTitle">Centro</h2>
          <div class="muted" id="centerSub"></div>
        </div>
        <div class="row">
          <button class="btn ghost" id="btnBackToCenters">← Centri</button>
          <button class="btn primary" id="btnNewLaser">+ Nuovo laser</button>
          <button class="btn primary" id="btnNewManipolo">+ Nuovo manipolo</button>
        </div>
      </div>

      <div class="summary-grid">
        <div class="summary-card">
          <div class="summary-label">Regione</div>
          <div class="summary-value" id="sumRegion">-</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Centro</div>
          <div class="summary-value" id="sumCenter">-</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Laser</div>
          <div class="summary-value" id="sumLaser">0</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Manipoli</div>
          <div class="summary-value" id="sumManipoli">0</div>
        </div>
      </div>

      <div class="two-col">
        <div>
          <div class="section-box">
            <div class="section-head">
              <h3>Laser del centro</h3>
            </div>
            <div class="items-grid" id="laserList"></div>
          </div>

          <div class="section-box">
            <div class="section-head">
              <h3>Manipoli del centro</h3>
            </div>
            <div class="items-grid" id="manipoliList"></div>
          </div>
        </div>

        <div>
          <div class="events-panel">
            <div class="section-head">
              <h3>Storico eventi del centro</h3>
            </div>
            <div class="event-list" id="eventsList"></div>
          </div>
        </div>
      </div>
    </section>

    <div class="modal hidden" id="itemModal">
      <div class="modal-card">
        <div class="modal-head">
          <div>
            <div class="brand-title" id="itemModalTitle">Elemento</div>
            <div class="brand-sub">Modifica i dati o registra un evento</div>
          </div>
          <button class="icon-btn" id="itemModalClose">✕</button>
        </div>

        <div class="editor-box" style="box-shadow:none;padding:0;border:0;background:transparent;">
          <div class="form-grid">
            <label>Tipo
              <select id="iType" class="input">
                <option value="LASER">LASER</option>
                <option value="MANIPOLO">MANIPOLO</option>
              </select>
            </label>
            <label>Stato
              <input id="iStatus" class="input" placeholder="ATTIVO / NON ATTIVO" />
            </label>
            <label>Seriale
              <input id="iSerial" class="input" placeholder="Codice seriale" />
            </label>
            <label>Regione
              <input id="iRegion" class="input" placeholder="Es. CAMPANIA / PIEMONTE / SEDE" />
            </label>
            <label>Centro / Città
              <input id="iLocation" class="input" placeholder="Es. Vomero / Magazzino / Sede" />
            </label>
            <label>Note
              <textarea id="iNote" class="input"></textarea>
            </label>
          </div>

          <div class="row" style="margin-top:14px;">
            <button class="btn primary" id="btnSaveItem">Salva</button>
            <button class="btn" id="btnShowEventForm">+ Aggiungi evento</button>
            <button class="btn danger hidden" id="btnDeleteItemFromModal">Rimuovi</button>
            <span class="muted" id="itemMsg"></span>
          </div>

          <div id="eventForm" class="hidden">
            <hr class="sep" />
            <div class="form-grid">
              <label>Tipo evento
                <input id="eType" class="input" placeholder="SPOSTAMENTO / MANUTENZIONE / ROTTURA" />
              </label>
              <label>Da
                <input id="eFrom" class="input" placeholder="Da centro" />
              </label>
              <label>A
                <input id="eTo" class="input" placeholder="A centro" />
              </label>
              <label>Note evento
                <textarea id="eNote" class="input"></textarea>
              </label>
            </div>
            <div class="row" style="margin-top:14px;">
              <button class="btn primary" id="btnSaveEvent">Registra evento</button>
              <span class="muted" id="eventMsg"></span>
            </div>
          </div>

          <hr class="sep" />
          <div class="section-head">
            <h3>Storico elemento</h3>
          </div>
          <div class="event-list" id="singleEvents"></div>
        </div>
      </div>
    </div>

    <div class="modal hidden" id="deleteModal">
      <div class="modal-card" style="max-width:520px;">
        <div class="modal-head">
          <div>
            <div class="brand-title">Conferma rimozione</div>
            <div class="brand-sub">Verrà eliminato anche lo storico eventi collegato.</div>
          </div>
          <button class="icon-btn" id="deleteModalClose">✕</button>
        </div>
        <div style="line-height:1.6;margin-bottom:14px;">
          Sei sicuro di voler rimuovere <strong id="deleteSerialName">questo elemento</strong>?
        </div>
        <div class="row">
          <button class="btn danger" id="deleteConfirm">Rimuovi</button>
          <button class="btn ghost" id="deleteCancel">Annulla</button>
        </div>
      </div>
    </div>

    <div class="modal hidden" id="centerAddModal">
      <div class="modal-card" style="max-width:520px;">
        <div class="modal-head">
          <div>
            <div class="brand-title">Aggiungi centro</div>
            <div class="brand-sub">Il centro verrà aggiunto alla regione selezionata.</div>
          </div>
          <button class="icon-btn" id="centerAddModalClose">✕</button>
        </div>
        <label>Nome centro
          <input id="newCenterName" class="input" placeholder="Es. Arezzo, Vomero, Cassino, Magazzino..." />
        </label>
        <div class="row" style="margin-top:14px;">
          <button class="btn primary" id="centerAddConfirm">Salva</button>
          <span class="muted" id="centerAddMsg"></span>
        </div>
      </div>
    </div>

    <div class="modal hidden" id="centerRemoveModal">
      <div class="modal-card" style="max-width:620px;">
        <div class="modal-head">
          <div>
            <div class="brand-title">Rimuovi centro</div>
            <div class="brand-sub">Il centro verrà nascosto dalla regione selezionata.</div>
          </div>
          <button class="icon-btn" id="centerRemoveModalClose">✕</button>
        </div>
        <label>Seleziona centro
          <select id="removeCenterSelect" class="input"></select>
        </label>
        <div class="row" style="margin-top:14px;">
          <button class="btn danger" id="centerRemoveConfirm">Rimuovi</button>
          <span class="muted" id="centerRemoveMsg"></span>
        </div>
      </div>
    </div>
  </main>

  <script src="/app.js?v=12"></script>
</body>
</html>
'''

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(content=HTML, headers=NO_CACHE_HEADERS)


@app.get("/style.css")
def style():
    return Response(content=CSS, media_type="text/css", headers=NO_CACHE_HEADERS)


@app.get("/app.js")
def script():
    return Response(content=JS, media_type="application/javascript", headers=NO_CACHE_HEADERS)


@app.get("/api/regions")
def get_regions():
    return [{"name": r} for r in REGIONS]


@app.get("/api/centers")
def get_centers(region: str, db: Session = Depends(get_db)):
    region = clean_region(region)

    item_rows = (
        db.query(Item.location)
        .filter(Item.region == region)
        .filter(Item.location.isnot(None))
        .filter(Item.location != "")
        .distinct()
        .all()
    )

    manual_rows = (
        db.query(Center.name)
        .filter(Center.region == region)
        .distinct()
        .all()
    )

    hidden_rows = (
        db.query(HiddenCenter.name)
        .filter(HiddenCenter.region == region)
        .distinct()
        .all()
    )

    hidden = {clean_center(r[0]) for r in hidden_rows if r[0]}
    names = set()

    for row in item_rows:
        name = clean_center(row[0])
        if name and name not in hidden:
            names.add(name)

    for row in manual_rows:
        name = clean_center(row[0])
        if name and name not in hidden:
            names.add(name)

    return [{"name": name} for name in sorted(names, key=lambda x: x.lower())]


@app.post("/api/centers")
def add_center(payload: CenterIn, db: Session = Depends(get_db)):
    region = clean_region(payload.region)
    name = clean_center(payload.name)

    if not region:
        raise HTTPException(status_code=400, detail="Regione obbligatoria")
    if not name:
        raise HTTPException(status_code=400, detail="Nome centro obbligatorio")

    hidden = db.query(HiddenCenter).filter(
        HiddenCenter.region == region,
        HiddenCenter.name == name
    ).first()
    if hidden:
        db.delete(hidden)
        db.flush()

    existing = db.query(Center).filter(
        Center.region == region,
        Center.name == name
    ).first()

    if not existing:
        db.add(Center(region=region, name=name))

    db.commit()
    return {"ok": True}


@app.delete("/api/centers/{region}/{center}")
def delete_center(region: str, center: str, db: Session = Depends(get_db)):
    region = clean_region(region)
    center = clean_center(center)

    if not center:
        raise HTTPException(status_code=400, detail="Centro non valido")

    manual = db.query(Center).filter(
        Center.region == region,
        Center.name == center
    ).first()
    if manual:
        db.delete(manual)
        db.flush()

    hidden = db.query(HiddenCenter).filter(
        HiddenCenter.region == region,
        HiddenCenter.name == center
    ).first()
    if not hidden:
        db.add(HiddenCenter(region=region, name=center))

    db.commit()
    return {"ok": True}


@app.get("/api/centers/manage/list")
def manage_centers_list(region: str, db: Session = Depends(get_db)):
    region = clean_region(region)

    item_rows = (
        db.query(Item.location)
        .filter(Item.region == region)
        .filter(Item.location.isnot(None))
        .filter(Item.location != "")
        .distinct()
        .all()
    )

    manual_rows = (
        db.query(Center.name)
        .filter(Center.region == region)
        .distinct()
        .all()
    )

    hidden_rows = (
        db.query(HiddenCenter.name)
        .filter(HiddenCenter.region == region)
        .distinct()
        .all()
    )

    hidden = {clean_center(r[0]) for r in hidden_rows if r[0]}
    manual = {clean_center(r[0]) for r in manual_rows if r[0]}
    item_based = {clean_center(r[0]) for r in item_rows if r[0]}

    names = sorted((manual | item_based) - hidden, key=lambda x: x.lower())

    return [
        {
            "name": n,
            "manual": n in manual,
            "from_items": n in item_based,
        }
        for n in names
    ]


@app.get("/api/centers/{region}/{center}")
def get_center_detail(region: str, center: str, db: Session = Depends(get_db)):
    region = clean_region(region)
    center = clean_center(center)

    items = (
        db.query(Item)
        .filter(Item.region == region, Item.location == center)
        .order_by(Item.type.asc(), Item.serial.asc())
        .all()
    )

    lasers = [item_to_dict(i) for i in items if i.type == "LASER"]
    manipoli = [item_to_dict(i) for i in items if i.type == "MANIPOLO"]

    events = (
        db.query(Event, Item.serial, Item.type)
        .join(Item, Item.id == Event.item_id)
        .filter(Item.region == region, Item.location == center)
        .order_by(Event.event_date.desc())
        .all()
    )

    return {
        "region": region,
        "center": center,
        "counts": {
            "laser": len(lasers),
            "manipoli": len(manipoli),
            "totale": len(items),
        },
        "lasers": lasers,
        "manipoli": manipoli,
        "events": [
            {
                "id": e.id,
                "event_date": e.event_date,
                "event_type": e.event_type,
                "from_location": e.from_location or "",
                "to_location": e.to_location or "",
                "note": e.note or "",
                "serial": serial,
                "item_type": item_type,
            }
            for e, serial, item_type in events
        ],
    }


@app.get("/api/items")
def list_items(
    type: str | None = None,
    q: str | None = None,
    region: str | None = None,
    center: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Item)
    if type:
        query = query.filter(Item.type == type)
    if region:
        query = query.filter(Item.region == clean_region(region))
    if center:
        query = query.filter(Item.location == clean_center(center))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Item.serial.like(like),
                Item.location.like(like),
                Item.status.like(like),
                Item.region.like(like),
                Item.note.like(like),
            )
        )
    items = query.order_by(Item.region.asc(), Item.location.asc(), Item.type.asc(), Item.serial.asc()).all()
    return [item_to_dict(i) for i in items]


@app.post("/api/items")
def add_item(payload: ItemIn, db: Session = Depends(get_db)):
    payload.region = clean_region(payload.region)
    payload.location = clean_center(payload.location)
    payload.serial = clean_serial(payload.serial)

    existing = (
        db.query(Item)
        .filter(func.upper(Item.serial) == payload.serial)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Seriale già presente")

    it = Item(**payload.model_dump())
    db.add(it)
    db.commit()
    db.refresh(it)
    return {"id": it.id}


@app.get("/api/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    it = db.get(Item, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Non trovato")

    events = sorted(it.events, key=lambda e: e.event_date, reverse=True)
    data = item_to_dict(it)
    data["events"] = [
        {
            "id": e.id,
            "event_date": e.event_date,
            "event_type": e.event_type,
            "from_location": e.from_location,
            "to_location": e.to_location,
            "note": e.note,
        }
        for e in events
    ]
    return data


@app.patch("/api/items/{item_id}")
def update_item(item_id: int, payload: ItemIn, db: Session = Depends(get_db)):
    it = db.get(Item, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Non trovato")

    payload.region = clean_region(payload.region)
    payload.location = clean_center(payload.location)
    payload.serial = clean_serial(payload.serial)

    current_serial = clean_serial(it.serial)

    if payload.serial != current_serial:
        existing = (
            db.query(Item)
            .filter(func.upper(Item.serial) == payload.serial)
            .filter(Item.id != item_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Seriale già presente")

    it.type = payload.type
    it.serial = payload.serial
    it.status = payload.status
    it.location = payload.location
    it.region = payload.region
    it.note = payload.note
    db.commit()
    return {"ok": True}


@app.delete("/api/items/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    it = db.get(Item, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Non trovato")

    db.query(Event).filter(Event.item_id == item_id).delete(synchronize_session=False)
    db.delete(it)
    db.commit()
    return Response(status_code=204)


@app.post("/api/items/{item_id}/events")
def add_event(item_id: int, payload: EventIn, db: Session = Depends(get_db)):
    it = db.get(Item, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Non trovato")

    ev = Event(item_id=item_id, **payload.model_dump())
    db.add(ev)

    if payload.to_location.strip():
        it.location = payload.to_location.strip()

    db.commit()
    return {"ok": True}