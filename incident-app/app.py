from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import psycopg2, psycopg2.extras, os, hashlib, threading, time
from datetime import datetime, timezone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supergeheim123")

DB = dict(
    host=os.environ.get("DB_HOST", "postgres"),
    database=os.environ.get("DB_NAME", "monitoring"),
    user=os.environ.get("DB_USER", "monitor"),
    password=os.environ.get("DB_PASSWORD", "changeme123")
)

MAIL_USER = os.environ.get("MAIL_USER", "")
MAIL_PASS = os.environ.get("MAIL_PASS", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "")
APP_URL   = os.environ.get("APP_URL", "http://localhost")
IT_CODE   = os.environ.get("IT_CODE", "it_for_users26")

KATEGORIEN = {
    "Software":                ["Citrix", "Microsoft 365", "SAP", "Adobe", "Sonstige"],
    "Hardware":                ["Laptop", "Drucker", "Monitor", "Peripherie", "Sonstige"],
    "Netzwerk":                ["VPN", "WLAN", "LAN", "Firewall", "Sonstige"],
    "Datenbank":               ["Backup", "Zugriff", "Performance", "Sonstige"],
    "Infrastruktur":           ["Docker", "Server", "Storage", "Virtualisierung", "Sonstige"],
    "Security":                ["Virus", "Phishing", "Zugriffsproblem", "Datenverlust", "Sonstige"],
    "Telefonie & Alarmierung": ["Festnetz", "Handy", "Alarmanlage", "Sonstige"],
}

# ================================================================
# DATENBANK
# ================================================================
def db():
    return psycopg2.connect(**DB)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    c = db(); cur = c.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id          SERIAL PRIMARY KEY,
        kuerzel     VARCHAR(20) UNIQUE NOT NULL,
        anzeigename VARCHAR(100),
        email       VARCHAR(255) UNIQUE NOT NULL,
        passwort    VARCHAR(255) NOT NULL,
        ist_it      BOOLEAN DEFAULT FALSE,
        erstellt_am TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS tickets (
        id               SERIAL PRIMARY KEY,
        nummer           VARCHAR(20) UNIQUE NOT NULL,
        erstellt_von_id  INT REFERENCES users(id),
        anrufer          VARCHAR(100),
        telefon          VARCHAR(50),
        kategorie        VARCHAR(100),
        unterkategorie   VARCHAR(100),
        prioritaet       VARCHAR(20) DEFAULT '4 - Niedrig',
        auswirkung       VARCHAR(20) DEFAULT '3 - Niedrig',
        dringlichkeit    VARCHAR(20) DEFAULT '3 - Niedrig',
        status           VARCHAR(50) DEFAULT 'Offen',
        zugewiesen_an    VARCHAR(100),
        kurzbeschreibung VARCHAR(255),
        beschreibung     TEXT,
        loesung          TEXT,
        erstellt_am      TIMESTAMPTZ DEFAULT NOW(),
        aktualisiert_am  TIMESTAMPTZ DEFAULT NOW(),
        geloest_am       TIMESTAMPTZ,
        geschlossen_am   TIMESTAMPTZ
    );
    CREATE TABLE IF NOT EXISTS notizen (
        id          SERIAL PRIMARY KEY,
        ticket_id   INT REFERENCES tickets(id) ON DELETE CASCADE,
        autor       VARCHAR(100),
        text        TEXT NOT NULL,
        intern      BOOLEAN DEFAULT FALSE,
        erstellt_am TIMESTAMPTZ DEFAULT NOW()
    );
    """)
    c.commit(); cur.close(); c.close()

def next_nummer():
    c = db(); cur = c.cursor()
    cur.execute("SELECT COUNT(*) FROM tickets")
    n = cur.fetchone()[0]
    cur.close(); c.close()
    return f"INC{str(n + 1).zfill(7)}"

def get_it_users():
    c = db(); cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT kuerzel, anzeigename FROM users WHERE ist_it=TRUE ORDER BY kuerzel")
    users = cur.fetchall()
    cur.close(); c.close()
    return users

# ================================================================
# MAIL
# ================================================================
def send_mail(to_email, subject, body):
    if not MAIL_USER or not MAIL_PASS or not to_email:
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_FROM or MAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(MAIL_USER, MAIL_PASS)
            s.send_message(msg)
    except Exception as e:
        print(f"Mail-Fehler: {e}")

def mail_notiz(ticket, notiz_text, user_email):
    subject = f"Neue Notiz zu Ticket {ticket['nummer']}"
    body = f"""Hallo {ticket['anrufer']},

zu deinem Ticket wurde eine neue Notiz hinzugefügt.

Ticket:       {ticket['nummer']}
Beschreibung: {ticket['kurzbeschreibung']}

Notiz:
{notiz_text}

Ticket ansehen: {APP_URL}/tickets/{ticket['id']}

Grüsse,
Incident System"""
    send_mail(user_email, subject, body)

def mail_geloest(ticket, geloest_von_name, user_email):
    subject = f"Dein Ticket {ticket['nummer']} wurde gelöst"
    body = f"""Hallo {ticket['anrufer']},

dein Ticket wurde gelöst.

Ticket:       {ticket['nummer']}
Beschreibung: {ticket['kurzbeschreibung']}
Gelöst von:   {geloest_von_name}

Lösungsnotiz:
{ticket['loesung'] or '(keine Lösungsnotiz erfasst)'}

Falls das Problem noch besteht, kannst du das Ticket innerhalb von 7 Tagen wieder öffnen:
{APP_URL}/tickets/{ticket['id']}

{geloest_von_name}"""
    send_mail(user_email, subject, body)

# ================================================================
# AUTO-CLOSE BACKGROUND JOB
# ================================================================
def auto_close_job():
    while True:
        try:
            c = db(); cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT id, nummer FROM tickets
                WHERE status = 'Gelöst'
                AND geloest_am IS NOT NULL
                AND geloest_am < NOW() - INTERVAL '7 days'
            """)
            tickets = cur.fetchall()
            for t in tickets:
                cur.execute("""
                    UPDATE tickets SET status='Abgeschlossen', geschlossen_am=NOW(),
                    aktualisiert_am=NOW() WHERE id=%s
                """, (t['id'],))
                cur.execute("""
                    INSERT INTO notizen (ticket_id, autor, text, intern)
                    VALUES (%s, %s, %s, false)
                """, (t['id'], 'System', 'Ticket wurde automatisch nach 7 Tagen geschlossen.'))
            c.commit(); cur.close(); c.close()
        except Exception as e:
            print(f"Auto-Close Fehler: {e}")
        time.sleep(3600)  # jede Stunde prüfen

# ================================================================
# AUTH HELPERS
# ================================================================
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def it_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('ist_it'):
            return redirect(url_for('start'))
        return f(*args, **kwargs)
    return decorated

# ================================================================
# ROUTEN – AUTH
# ================================================================
@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        action  = request.form.get("action")
        kuerzel = request.form.get("kuerzel", "").strip().upper()
        pw      = hash_pw(request.form.get("passwort", ""))
        c = db(); cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if action == "register":
            email       = request.form.get("email", "").strip().lower()
            anzeigename = request.form.get("anzeigename", "").strip()
            it_eingabe  = request.form.get("it_code", "").strip()
            ist_it      = it_eingabe == IT_CODE
            if not email:
                error = "E-Mail ist ein Pflichtfeld."
            else:
                try:
                    cur.execute("""
                        INSERT INTO users (kuerzel, anzeigename, email, passwort, ist_it)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (kuerzel, anzeigename or kuerzel, email, pw, ist_it))
                    c.commit()
                    cur.execute("SELECT * FROM users WHERE kuerzel=%s", (kuerzel,))
                    u = cur.fetchone()
                    session['user_id']     = u['id']
                    session['kuerzel']     = u['kuerzel']
                    session['anzeigename'] = u['anzeigename']
                    session['email']       = u['email']
                    session['ist_it']      = u['ist_it']
                    return redirect(url_for('start'))
                except Exception as e:
                    if "kuerzel" in str(e):
                        error = "Dieses Kürzel ist bereits vergeben."
                    elif "email" in str(e):
                        error = "Diese E-Mail-Adresse ist bereits registriert."
                    else:
                        error = "Fehler bei der Registrierung."
        else:
            cur.execute("SELECT * FROM users WHERE kuerzel=%s AND passwort=%s", (kuerzel, pw))
            u = cur.fetchone()
            if u:
                session['user_id']     = u['id']
                session['kuerzel']     = u['kuerzel']
                session['anzeigename'] = u['anzeigename']
                session['email']       = u['email']
                session['ist_it']      = u['ist_it']
                return redirect(url_for('start'))
            else:
                error = "Kürzel oder Passwort falsch."
        cur.close(); c.close()
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# ================================================================
# ROUTEN – SEITEN
# ================================================================
@app.route("/start")
@login_required
def start():
    return render_template("start.html")

@app.route("/tickets/neu", methods=["GET", "POST"])
@login_required
def ticket_neu():
    if request.method == "POST":
        c = db(); cur = c.cursor()
        num = next_nummer()
        cur.execute("""
            INSERT INTO tickets
            (nummer, erstellt_von_id, anrufer, telefon, kategorie, unterkategorie,
             prioritaet, auswirkung, dringlichkeit, status, kurzbeschreibung, beschreibung)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Offen',%s,%s)
        """, (
            num, session['user_id'],
            request.form.get("anrufer") or session['anzeigename'],
            request.form.get("telefon"),
            request.form.get("kategorie"),
            request.form.get("unterkategorie"),
            request.form.get("prioritaet", "4 - Niedrig"),
            request.form.get("auswirkung", "3 - Niedrig"),
            request.form.get("dringlichkeit", "3 - Niedrig"),
            request.form.get("kurzbeschreibung"),
            request.form.get("beschreibung"),
        ))
        cur.execute("SELECT id FROM tickets WHERE nummer=%s", (num,))
        tid = cur.fetchone()[0]
        cur.execute("""
            INSERT INTO notizen (ticket_id, autor, text, intern)
            VALUES (%s, %s, %s, false)
        """, (tid, session['kuerzel'], "Ticket wurde erstellt."))
        c.commit(); cur.close(); c.close()
        flash(f"Ticket {num} wurde erfolgreich erstellt.", "success")
        return redirect(url_for('meine_tickets'))
    return render_template("ticket_neu.html", kategorien=KATEGORIEN)

@app.route("/tickets/meine")
@login_required
def meine_tickets():
    c = db(); cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM tickets WHERE erstellt_von_id=%s ORDER BY erstellt_am DESC
    """, (session['user_id'],))
    tickets = cur.fetchall()
    cur.close(); c.close()
    return render_template("meine_tickets.html", tickets=tickets)

@app.route("/dashboard")
@login_required
@it_required
def dashboard():
    c = db(); cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as n FROM tickets WHERE status='Offen'")
    offen = cur.fetchone()['n']
    cur.execute("SELECT COUNT(*) as n FROM tickets WHERE status='In Bearbeitung'")
    in_bearbeitung = cur.fetchone()['n']
    cur.execute("SELECT COUNT(*) as n FROM tickets WHERE status='Gelöst'")
    geloest = cur.fetchone()['n']
    cur.execute("SELECT COUNT(*) as n FROM tickets WHERE (zugewiesen_an IS NULL OR zugewiesen_an='') AND status='Offen'")
    neu_unzugew = cur.fetchone()['n']
    cur.execute("SELECT COUNT(*) as n FROM tickets WHERE zugewiesen_an=%(k)s AND status != 'Abgeschlossen'", {'k': session['kuerzel']})
    mein_pool_count = cur.fetchone()['n']
    cur.execute("SELECT * FROM tickets WHERE status='Offen' ORDER BY erstellt_am DESC LIMIT 15")
    neue = cur.fetchall()
    cur.execute("SELECT * FROM tickets WHERE zugewiesen_an=%s AND status NOT IN ('Gelöst','Abgeschlossen') ORDER BY erstellt_am DESC", (session['kuerzel'],))
    meine = cur.fetchall()
    cur.execute("SELECT * FROM tickets WHERE status='Offen' ORDER BY erstellt_am DESC")
    alle_offen = cur.fetchall()
    cur.close(); c.close()
    return render_template("dashboard.html",
        offen=offen, in_bearbeitung=in_bearbeitung, geloest=geloest,
        neu_unzugew=neu_unzugew, mein_pool_count=mein_pool_count,
        neue=neue, meine=meine, alle_offen=alle_offen)

@app.route("/tickets/<int:id>", methods=["GET", "POST"])
@login_required
def ticket_detail(id):
    c = db(); cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update" and session.get('ist_it'):
            neuer_status = request.form.get("status")
            cur.execute("SELECT * FROM tickets WHERE id=%s", (id,))
            alter_status = cur.fetchone()['status']
            geloest_am = None
            if neuer_status == "Gelöst" and alter_status != "Gelöst":
                geloest_am = datetime.now()
            elif neuer_status != "Gelöst":
                geloest_am = None

            cur.execute("""
                UPDATE tickets SET
                    kategorie=%s, unterkategorie=%s, prioritaet=%s, auswirkung=%s,
                    dringlichkeit=%s, status=%s, zugewiesen_an=%s,
                    kurzbeschreibung=%s, beschreibung=%s, loesung=%s,
                    geloest_am=COALESCE(%s, geloest_am),
                    aktualisiert_am=NOW()
                WHERE id=%s
            """, (
                request.form.get("kategorie"),
                request.form.get("unterkategorie"),
                request.form.get("prioritaet"),
                request.form.get("auswirkung"),
                request.form.get("dringlichkeit"),
                neuer_status,
                request.form.get("zugewiesen_an"),
                request.form.get("kurzbeschreibung"),
                request.form.get("beschreibung"),
                request.form.get("loesung"),
                geloest_am,
                id
            ))
            cur.execute("""
                INSERT INTO notizen (ticket_id, autor, text, intern)
                VALUES (%s, %s, %s, true)
            """, (id, session['kuerzel'], f"Status geändert zu: {neuer_status}"))

            # Mail wenn gelöst
            if neuer_status == "Gelöst" and alter_status != "Gelöst":
                cur.execute("SELECT * FROM tickets WHERE id=%s", (id,))
                t = cur.fetchone()
                cur.execute("SELECT email FROM users WHERE id=%s", (t['erstellt_von_id'],))
                u = cur.fetchone()
                if u and u['email']:
                    geloest_von = session.get('anzeigename') or session['kuerzel']
                    c.commit()
                    threading.Thread(
                        target=mail_geloest,
                        args=(t, geloest_von, u['email']),
                        daemon=True
                    ).start()

            c.commit()

        elif action == "notiz":
            intern = request.form.get("intern") == "on"
            notiz_text = request.form.get("text", "")
            cur.execute("""
                INSERT INTO notizen (ticket_id, autor, text, intern)
                VALUES (%s, %s, %s, %s)
            """, (id, session['kuerzel'], notiz_text, intern))
            c.commit()

            # Mail an Ersteller bei neuer (nicht-interner) Notiz
            if not intern:
                cur.execute("SELECT * FROM tickets WHERE id=%s", (id,))
                t = cur.fetchone()
                cur.execute("SELECT email FROM users WHERE id=%s", (t['erstellt_von_id'],))
                u = cur.fetchone()
                if u and u['email'] and t['erstellt_von_id'] != session['user_id']:
                    threading.Thread(
                        target=mail_notiz,
                        args=(t, notiz_text, u['email']),
                        daemon=True
                    ).start()

        elif action == "reopen":
            cur.execute("""
                UPDATE tickets SET status='Offen', geloest_am=NULL, aktualisiert_am=NOW()
                WHERE id=%s AND status='Gelöst'
                AND geloest_am > NOW() - INTERVAL '7 days'
            """, (id,))
            cur.execute("""
                INSERT INTO notizen (ticket_id, autor, text, intern)
                VALUES (%s, %s, %s, false)
            """, (id, session['kuerzel'], "Ticket wurde vom Benutzer wieder geöffnet."))
            c.commit()

        cur.close(); c.close()
        return redirect(url_for('ticket_detail', id=id))

    # GET
    cur.execute("SELECT * FROM tickets WHERE id=%s", (id,))
    t = cur.fetchone()
    cur.execute("SELECT * FROM notizen WHERE ticket_id=%s ORDER BY erstellt_am ASC", (id,))
    notizen = cur.fetchall()
    it_users = get_it_users()
    cur.close(); c.close()

    if not t:
        return redirect(url_for('start'))
    if not session.get('ist_it') and t['erstellt_von_id'] != session['user_id']:
        return redirect(url_for('start'))

    # Kann User noch wieder öffnen?
    kann_reopenen = False
    if t['status'] == 'Gelöst' and t['geloest_am']:
        diff = datetime.now(timezone.utc) - t['geloest_am'].replace(tzinfo=timezone.utc)
        kann_reopenen = diff.days < 7

    return render_template("ticket_detail.html",
        t=t, notizen=notizen, kategorien=KATEGORIEN,
        it_users=it_users, kann_reopenen=kann_reopenen)

# ================================================================
# TICKET LISTE (IT) – filterbar + sortierbar
# ================================================================
@app.route("/tickets/liste")
@login_required
@it_required
def ticket_liste():
    status_filter = request.args.get("status", "")
    c = db(); cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Filter-Parameter
    f_nummer    = request.args.get("f_nummer", "").strip()
    f_person    = request.args.get("f_person", "").strip()
    f_beschr    = request.args.get("f_beschr", "").strip()
    f_status    = request.args.get("f_status", "").strip()
    f_zugewiesen= request.args.get("f_zugewiesen", "").strip()
    sort_col    = request.args.get("sort", "erstellt_am")
    sort_dir    = request.args.get("dir", "desc")

    allowed_cols = ["nummer", "anrufer", "kurzbeschreibung", "status", "zugewiesen_an", "aktualisiert_am", "erstellt_am"]
    if sort_col not in allowed_cols:
        sort_col = "erstellt_am"
    if sort_dir not in ["asc", "desc"]:
        sort_dir = "desc"

    query = "SELECT * FROM tickets WHERE 1=1"
    params = []

    if status_filter:
        query += " AND status=%s"; params.append(status_filter)
    if f_nummer:
        query += " AND LOWER(nummer) LIKE %s"; params.append(f"%{f_nummer.lower()}%")
    if f_person:
        query += " AND LOWER(anrufer) LIKE %s"; params.append(f"%{f_person.lower()}%")
    if f_beschr:
        query += " AND LOWER(kurzbeschreibung) LIKE %s"; params.append(f"%{f_beschr.lower()}%")
    if f_status:
        query += " AND LOWER(status) LIKE %s"; params.append(f"%{f_status.lower()}%")
    if f_zugewiesen:
        query += " AND LOWER(zugewiesen_an) LIKE %s"; params.append(f"%{f_zugewiesen.lower()}%")

    query += f" ORDER BY {sort_col} {sort_dir}"
    cur.execute(query, params)
    tickets = cur.fetchall()
    cur.close(); c.close()

    titel_map = {
        "Offen": "Offene Tickets",
        "In Bearbeitung": "Tickets in Bearbeitung",
        "Gelöst": "Gelöste Tickets",
        "Abgeschlossen": "Abgeschlossene Tickets",
        "": "Alle Tickets"
    }

    return render_template("ticket_liste.html",
        tickets=tickets, status_filter=status_filter,
        titel=titel_map.get(status_filter, "Tickets"),
        sort_col=sort_col, sort_dir=sort_dir,
        f_nummer=f_nummer, f_person=f_person, f_beschr=f_beschr,
        f_status=f_status, f_zugewiesen=f_zugewiesen)

# ================================================================
# PROFIL
# ================================================================
@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    error = None
    success = None
    if request.method == "POST":
        action = request.form.get("action")
        c = db(); cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if action == "passwort":
            altes_pw = hash_pw(request.form.get("altes_pw", ""))
            neues_pw = request.form.get("neues_pw", "")
            neues_pw2 = request.form.get("neues_pw2", "")
            cur.execute("SELECT passwort FROM users WHERE id=%s", (session['user_id'],))
            u = cur.fetchone()
            if u['passwort'] != altes_pw:
                error = "Altes Passwort ist falsch."
            elif neues_pw != neues_pw2:
                error = "Neue Passwörter stimmen nicht überein."
            elif len(neues_pw) < 4:
                error = "Neues Passwort muss mindestens 4 Zeichen haben."
            else:
                cur.execute("UPDATE users SET passwort=%s WHERE id=%s", (hash_pw(neues_pw), session['user_id']))
                c.commit()
                success = "Passwort wurde erfolgreich geändert."

        elif action == "profil":
            anzeigename = request.form.get("anzeigename", "").strip()
            email = request.form.get("email", "").strip().lower()
            if not email:
                error = "E-Mail darf nicht leer sein."
            else:
                try:
                    cur.execute("UPDATE users SET anzeigename=%s, email=%s WHERE id=%s",
                                (anzeigename or session['kuerzel'], email, session['user_id']))
                    c.commit()
                    session['anzeigename'] = anzeigename or session['kuerzel']
                    session['email'] = email
                    success = "Profil wurde gespeichert."
                except:
                    error = "Diese E-Mail-Adresse ist bereits vergeben."

        cur.close(); c.close()

    c = db(); cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cur.fetchone()
    cur.close(); c.close()
    return render_template("profil.html", user=user, error=error, success=success)

# ================================================================
# API
# ================================================================
@app.route("/api/unterkategorien/<kat>")
def unterkategorien(kat):
    return jsonify(KATEGORIEN.get(kat, []))

# ================================================================
# START
# ================================================================
if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=auto_close_job, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
