"""
actualizar_metricas.py
Script de automatización integral para @tintaysoda.stream
Procesa todas las exportaciones oficiales de Meta Business Suite (CSV / XLSX),
anexa períodos históricos acumulados (Agosto, Septiembre, Octubre, Noviembre, etc.),
segmenta dinámicamente por meses y por semanas, calcula la comparativa mes a mes (MoM),
y actualiza tanto el JSON como el panel interactivo dashboard.html.
"""

import os
import sys
import glob
import json
import re
import csv
from datetime import datetime, timedelta

# Asegurar encoding UTF-8 en consola para evitar errores con caracteres especiales en Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
METRICAS_DIR = os.path.join(BASE_DIR, "metricas")
JSON_OUTPUT = os.path.join(METRICAS_DIR, "historico_metricas.json")
RAW_JSON_OUTPUT = os.path.join(METRICAS_DIR, "historico_crudo.json")
SNAPSHOTS_JSON = os.path.join(METRICAS_DIR, "historico_snapshots.json")
HTML_OUTPUT = os.path.join(METRICAS_DIR, "dashboard.html")
INDEX_OUTPUT = os.path.join(METRICAS_DIR, "index.html")
ROOT_INDEX = os.path.join(BASE_DIR, "index.html")
MANUAL_DURATIONS_JSON = os.path.join(METRICAS_DIR, "duraciones_manuales.json")

MONTH_NAMES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}
MONTH_SHORT_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Ago",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
}

MONTH_REV_ES = {v.lower(): k for k, v in MONTH_NAMES_ES.items()}


def normalize_column_name(col):
    if col is None:
        return ""
    c = str(col).lower().strip()
    c = c.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    c = re.sub(r"[^a-z0-9]", "_", c)
    c = re.sub(r"_+", "_", c).strip("_")
    return c


def load_file(file_path):
    encodings = ["utf-8-sig", "utf-8", "latin1", "cp1252", "iso-8859-1"]
    for enc in encodings:
        for sep in [",", ";", "\t"]:
            try:
                with open(file_path, "r", encoding=enc, newline="") as f:
                    reader = csv.reader(f, delimiter=sep)
                    header = next(reader, None)
                    if header and len(header) >= 3:
                        f.seek(0)
                        dict_reader = csv.DictReader(f, delimiter=sep)
                        rows = list(dict_reader)
                        if rows:
                            return rows
            except Exception:
                continue
    return []


def classify_topic(title, full_text):
    text = (str(title) + " " + str(full_text)).lower()
    if any(k in text for k in ["gamer", "drones", "thiel", "palantir", "gotham", "armas", "guerra", "ucrania", "mendoza", "refugio", "paypal"]):
        return "Tecnodistopía & Geopolítica"
    elif any(k in text for k in ["indec", "milei", "natalidad", "hijo", "crianza", "tierras", "la plata", "uca", "sifilis", "salud"]):
        return "Datos Duros & Desmitificación"
    elif any(k in text for k in ["ansiedad", "hora", "plata virtual", "billeteras", "apuestas", "esperar", "concentrarte", "tiktok"]):
        return "Hábitos & Ansiedad Digital"
    else:
        return "Rosca Política & Sociedad"


def assign_temporal_groups(dt_arg, dt_now=None):
    if not dt_arg:
        return "Sin fecha", "Sin fecha"
    
    # Alinear año a la línea de tiempo auditada del canal (2026)
    year = 2026
    month = dt_arg.month

    month_name = MONTH_NAMES_ES.get(month, "Desconocido")
    month_label = f"{month_name} {year}"

    # Normalizar a 2026 para cálculo de semanas Lunes a Domingo
    dt_norm = dt_arg.replace(year=2026)
    monday = dt_norm - timedelta(days=dt_norm.weekday())
    sunday = monday + timedelta(days=6)

    # Semana auditada oficial del canal: Semana 1 arranca el Lunes 10 de Agosto de 2026
    base_monday = datetime(2026, 8, 10)
    diff_days = (monday.date() - base_monday.date()).days
    week_num = (diff_days // 7) + 1

    m_mon = MONTH_SHORT_ES.get(monday.month, "")
    m_sun = MONTH_SHORT_ES.get(sunday.month, "")

    if m_mon == m_sun:
        range_str = f"{monday.day:02d}-{sunday.day:02d} {m_mon}"
    else:
        range_str = f"{monday.day:02d} {m_mon} - {sunday.day:02d} {m_sun}"

    if dt_now is None:
        dt_now = datetime.now().replace(year=2026)
    else:
        dt_now = dt_now.replace(year=2026)
    now_monday = dt_now - timedelta(days=dt_now.weekday())

    is_ongoing = (monday.date() == now_monday.date()) and (dt_now < sunday.replace(hour=23, minute=59, second=59))
    suffix = " (En curso)" if is_ongoing else ""

    if week_num >= 1:
        week_label = f"Semana {week_num} ({range_str}){suffix}"
    else:
        week_label = f"Semana ({range_str}){suffix}"

    return month_label, week_label


def get_month_sort_key(month_str):
    parts = str(month_str).strip().split()
    if len(parts) == 2:
        m_name = parts[0].lower()
        y_str = parts[1]
        m_num = MONTH_REV_ES.get(m_name, 0)
        try:
            return int(y_str) * 100 + m_num
        except ValueError:
            return 0
    return 0


def get_last_completed_sunday(dt_now=None):
    if dt_now is None:
        dt_now = datetime.now()
    dt_now = dt_now.replace(year=2026)
    days_since_sunday = (dt_now.weekday() + 1) if dt_now.weekday() != 6 else 7
    last_sunday = (dt_now - timedelta(days=days_since_sunday)).date()
    return datetime(last_sunday.year, last_sunday.month, last_sunday.day, 23, 59, 59)


def process_all_exports():
    if not os.path.exists(METRICAS_DIR):
        print(f"[ERROR] No existe la carpeta {METRICAS_DIR}")
        sys.exit(1)

    all_files = glob.glob(os.path.join(METRICAS_DIR, "*.csv")) + glob.glob(os.path.join(METRICAS_DIR, "*.xlsx"))
    if not all_files:
        print("[ERROR] No se encontraron archivos .csv o .xlsx en metricas/")
        sys.exit(1)

    print(f"[INFO] Archivos encontrados: {[os.path.basename(f) for f in all_files]}")

    posts_by_id = {}

    if os.path.exists(RAW_JSON_OUTPUT):
        try:
            with open(RAW_JSON_OUTPUT, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                for rp in raw_data.get("posts", []):
                    r_id = str(rp.get("post_id", ""))
                    if r_id:
                        posts_by_id[r_id] = rp
            print(f"[INFO] Se precargaron {len(posts_by_id)} publicaciones del pool crudo.")
        except Exception:
            pass

    manual_durations = {}
    if os.path.exists(MANUAL_DURATIONS_JSON):
        try:
            with open(MANUAL_DURATIONS_JSON, "r", encoding="utf-8") as f:
                manual_durations = json.load(f)
        except Exception:
            pass

    for file_path in sorted(all_files):
        try:
            rows = load_file(file_path)
            if not rows:
                print(f"[WARN] No se pudieron extraer filas de {file_path}")
                continue
        except Exception as e:
            print(f"[WARN] No se pudo leer {file_path}: {e}")
            continue

        sample_row = rows[0]
        col_map = {normalize_column_name(col): col for col in sample_row.keys() if col}

        def get_val(row, candidate_keys, default=0, is_numeric=True):
            for k in candidate_keys:
                norm_k = normalize_column_name(k)
                for col_norm, col_orig in col_map.items():
                    if norm_k == col_norm or norm_k in col_norm:
                        val = row.get(col_orig, None)
                        if val is None or str(val).strip() == "":
                            return default
                        if is_numeric:
                            try:
                                val_str = str(val).replace(".", "").replace(",", ".").replace("%", "").strip()
                                return float(val_str)
                            except ValueError:
                                return default
                        return str(val).strip()
            return default

        for row in rows:
            post_id = str(get_val(row, ["identificador_de_la_publicacion", "post_id", "id"], default="", is_numeric=False)).strip()
            if not post_id or post_id == "0":
                continue

            raw_desc = get_val(row, ["descripcion", "description", "title", "titulo"], default="", is_numeric=False)
            clean_title = ""
            for line in raw_desc.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    clean_title = line
                    break
            if not clean_title:
                clean_title = f"Publicación #{post_id[-6:]}"

            date_raw = get_val(row, ["hora_de_publicacion", "publish_time", "fecha"], default="", is_numeric=False)
            dt_arg = None
            date_arg_str = date_raw
            if date_raw:
                for date_fmt in ["%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"]:
                    try:
                        dt = datetime.strptime(date_raw, date_fmt)
                        dt_arg = dt + timedelta(hours=4)  # PDT a UTC-3 Argentina
                        date_arg_str = dt_arg.strftime("%d/%m/%Y %H:%M hs")
                        break
                    except Exception:
                        continue

            duration_sec = int(get_val(row, ["duracion_segundos", "duracion"]))
            permalink = get_val(row, ["enlace_permanente", "permalink"], default="", is_numeric=False)
            post_type = get_val(row, ["tipo_de_publicacion", "post_type"], default="Reel", is_numeric=False)
            clean_type = "Reel" if "reel" in post_type.lower() or "video" in post_type.lower() else "Carrusel"

            if clean_type == "Carrusel":
                duration_sec = 0
                duration_str = "Carrusel"
            elif post_id in manual_durations and duration_sec <= 0:
                duration_sec = manual_durations[post_id].get("duration_sec", 0)
                duration_str = manual_durations[post_id].get("duration_str", f"{duration_sec} seg")
            elif duration_sec > 0:
                duration_str = f"{duration_sec} seg"
            else:
                duration_str = "-"

            views = int(get_val(row, ["visualizaciones", "views", "plays"]))
            reach = int(get_val(row, ["alcance", "reach"]))
            likes = int(get_val(row, ["me_gusta", "likes"]))
            shares = int(get_val(row, ["veces_que_se_compartio", "shares"]))
            saves = int(get_val(row, ["veces_que_se_guardo", "saves"]))
            comments = int(get_val(row, ["comentarios", "comments"]))
            follows = int(get_val(row, ["seguimientos", "follows"]))

            interactions = likes + shares + saves + comments
            save_rate = round((saves / views * 100), 2) if views > 0 else 0
            share_rate = round((shares / views * 100), 2) if views > 0 else 0
            engagement_rate = round((interactions / views * 100), 2) if views > 0 else 0

            month_label, week_label = assign_temporal_groups(dt_arg)
            topic = classify_topic(clean_title, raw_desc)

            post_obj = {
                "post_id": post_id,
                "title": clean_title,
                "full_text": raw_desc,
                "date": date_arg_str,
                "date_dt": dt_arg.strftime("%Y-%m-%d %H:%M") if dt_arg else "1970-01-01",
                "month": month_label,
                "week": week_label,
                "topic": topic,
                "type": clean_type,
                "permalink": permalink,
                "duration_sec": duration_sec,
                "duration_str": duration_str,
                "views": views,
                "reach": reach,
                "interactions": interactions,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "saves": saves,
                "follows": follows,
                "save_rate_pct": save_rate,
                "share_rate_pct": share_rate,
                "engagement_rate_pct": engagement_rate
            }

            # Deduplicación: conservar el registro con mayor número de visualizaciones
            if post_id in posts_by_id:
                if views >= posts_by_id[post_id]["views"]:
                    posts_by_id[post_id] = post_obj
            else:
                posts_by_id[post_id] = post_obj

    all_posts = list(posts_by_id.values())
    for p in all_posts:
        pid = str(p.get("post_id", ""))
        p_type = str(p.get("type", "")).lower()
        if "carrusel" in p_type or "carousel" in p_type or "album" in p_type:
            p["duration_str"] = "Carrusel"
            p["duration_sec"] = 0
        elif pid in manual_durations and (p.get("duration_sec", 0) <= 0 or p.get("duration_str") in ["-", ""]):
            p["duration_sec"] = manual_durations[pid].get("duration_sec", p.get("duration_sec", 0))
            p["duration_str"] = manual_durations[pid].get("duration_str", f"{p['duration_sec']} seg")
        elif p.get("duration_sec", 0) > 0 and (p.get("duration_str") in ["-", ""] or not p.get("duration_str")):
            p["duration_str"] = f"{p['duration_sec']} seg"

    all_posts.sort(key=lambda x: x["views"], reverse=True)
    for idx, p in enumerate(all_posts):
        p["rank"] = idx + 1

    # Cargar snapshots para calcular deltas de crecimiento reciente y catálogo
    snapshots_dict = {}
    if os.path.exists(SNAPSHOTS_JSON):
        try:
            with open(SNAPSHOTS_JSON, "r", encoding="utf-8") as f:
                snapshots_dict = json.load(f).get("snapshots", {})
        except Exception:
            pass

    sorted_snap_dates = sorted(snapshots_dict.keys())
    ref_snap = snapshots_dict.get(sorted_snap_dates[0], {}) if sorted_snap_dates else {}

    for p in all_posts:
        pid = str(p.get("post_id", ""))
        v_curr = p.get("views", 0)
        v_old = ref_snap.get(pid, {}).get("views", v_curr) if ref_snap else v_curr
        growth_7d = max(0, v_curr - v_old)
        p["growth_7d_views"] = growth_7d
        is_cur_week = "en curso" in p.get("week", "").lower()
        p["is_evergreen"] = bool(growth_7d >= 50 and not is_cur_week)

    # Detección y ordenación dinámica de TODOS los meses presentes
    detected_months = list(set(p["month"] for p in all_posts if p["month"] != "Sin fecha"))
    months_list = sorted(detected_months, key=get_month_sort_key)

    monthly_stats = {}
    for idx, m in enumerate(months_list):
        m_posts = [p for p in all_posts if p["month"] == m]
        m_count = len(m_posts)
        m_views = sum(p["views"] for p in m_posts)
        m_reach = sum(p["reach"] for p in m_posts)
        m_interactions = sum(p["interactions"] for p in m_posts)
        m_shares = sum(p["shares"] for p in m_posts)
        m_saves = sum(p["saves"] for p in m_posts)
        m_comments = sum(p["comments"] for p in m_posts)
        m_likes = sum(p["likes"] for p in m_posts)
        m_follows = sum(p["follows"] for p in m_posts)

        avg_views = int(m_views / m_count) if m_count > 0 else 0
        avg_shares = round(m_shares / m_count, 1) if m_count > 0 else 0
        avg_saves = round(m_saves / m_count, 1) if m_count > 0 else 0
        avg_comments = round(m_comments / m_count, 1) if m_count > 0 else 0

        top_post = max(m_posts, key=lambda x: x["views"]) if m_posts else None

        # Cálculo dinámico MoM (frente al mes calendario previo si existe)
        crecimiento_mom = None
        if idx > 0:
            prev_m = months_list[idx - 1]
            prev_stat = monthly_stats.get(prev_m, {})
            prev_avg_views = prev_stat.get("avg_views_per_post", 0)
            prev_avg_shares = prev_stat.get("avg_shares_per_post", 0)
            prev_avg_saves = prev_stat.get("avg_saves_per_post", 0)
            prev_avg_comms = prev_stat.get("avg_comments_per_post", 0)

            def calc_var(curr, prev):
                if prev > 0:
                    val = round(((curr - prev) / prev) * 100, 1)
                    return f"+{val}%" if val > 0 else f"{val}%"
                return "+100%" if curr > 0 else "0%"

            crecimiento_mom = {
                "mes_referencia": prev_m,
                "views_promedio": calc_var(avg_views, prev_avg_views),
                "shares_promedio": calc_var(avg_shares, prev_avg_shares),
                "saves_promedio": calc_var(avg_saves, prev_avg_saves),
                "comments_promedio": calc_var(avg_comments, prev_avg_comms)
            }

        monthly_stats[m] = {
            "month": m,
            "posts_count": m_count,
            "total_views": m_views,
            "avg_views_per_post": avg_views,
            "total_reach": m_reach,
            "total_interactions": m_interactions,
            "avg_interactions_per_post": int(m_interactions / m_count) if m_count > 0 else 0,
            "total_shares": m_shares,
            "avg_shares_per_post": avg_shares,
            "total_saves": m_saves,
            "avg_saves_per_post": avg_saves,
            "total_comments": m_comments,
            "avg_comments_per_post": avg_comments,
            "total_likes": m_likes,
            "total_follows": m_follows,
            "save_rate_pct": round(m_saves / m_views * 100, 2) if m_views > 0 else 0,
            "share_rate_pct": round(m_shares / m_views * 100, 2) if m_views > 0 else 0,
            "engagement_rate_pct": round(m_interactions / m_views * 100, 2) if m_views > 0 else 0,
            "crecimiento_vs_mes_anterior": crecimiento_mom,
            "top_performer": {
                "title": top_post["title"],
                "views": top_post["views"],
                "shares": top_post["shares"],
                "saves": top_post["saves"],
                "comments": top_post["comments"],
                "duration_str": top_post["duration_str"]
            } if top_post else None
        }

    # Agrupamiento SEMANAL dinámico
    def get_week_min_date(w_name):
        w_posts = [p for p in all_posts if p["week"] == w_name]
        return min(p["date_dt"] for p in w_posts) if w_posts else "9999"

    detected_weeks = list(set(p["week"] for p in all_posts if p["week"] != "Sin fecha"))
    weeks_order = sorted(detected_weeks, key=get_week_min_date)

    weeks_stats = {}
    for w in weeks_order:
        w_posts = [p for p in all_posts if p["week"] == w]
        w_count = len(w_posts)
        w_views = sum(p["views"] for p in w_posts)
        w_reach = sum(p["reach"] for p in w_posts)
        w_interactions = sum(p["interactions"] for p in w_posts)
        w_shares = sum(p["shares"] for p in w_posts)
        w_saves = sum(p["saves"] for p in w_posts)
        w_comments = sum(p["comments"] for p in w_posts)
        w_likes = sum(p["likes"] for p in w_posts)
        w_follows = sum(p.get("follows", 0) for p in w_posts)

        top_w = max(w_posts, key=lambda x: x["views"]) if w_posts else None

        # Crecimiento de catálogo antiguo durante esta semana
        w_min_date = min((p.get("date_dt") or "9999") for p in w_posts) if w_posts else "9999"
        prior_posts = [p for p in all_posts if (p.get("date_dt") or "9999") < w_min_date]

        catalog_growth_views = 0
        catalog_growers = []

        if "07-13 sep" in w.lower():
            s_start = snapshots_dict.get("2026-09-08", {})
            s_end = snapshots_dict.get("2026-09-15", {})
            for pp in prior_posts:
                ppid = str(pp.get("post_id", ""))
                v_s = s_start.get(ppid, {}).get("views", 0)
                v_e = s_end.get(ppid, {}).get("views", pp.get("views", 0))
                diff = v_e - v_s
                if diff > 0:
                    catalog_growth_views += diff
                    catalog_growers.append({
                        "post_id": ppid,
                        "title": pp.get("title", ""),
                        "growth": diff,
                        "original_week": pp.get("week", "")
                    })
        elif "en curso" in w.lower():
            s_start = snapshots_dict.get("2026-09-15", {})
            for pp in prior_posts:
                ppid = str(pp.get("post_id", ""))
                v_s = s_start.get(ppid, {}).get("views", 0)
                diff = pp.get("views", 0) - v_s
                if diff > 0:
                    catalog_growth_views += diff
                    catalog_growers.append({
                        "post_id": ppid,
                        "title": pp.get("title", ""),
                        "growth": diff,
                        "original_week": pp.get("week", "")
                    })

        catalog_growers.sort(key=lambda x: x["growth"], reverse=True)
        total_consumption = w_views + catalog_growth_views

        weeks_stats[w] = {
            "week": w,
            "posts_count": w_count,
            "total_views": total_consumption,
            "views_new_posts": w_views,
            "views_catalog_growth": catalog_growth_views,
            "total_consumption_views": total_consumption,
            "avg_views_per_post": int(w_views / w_count) if w_count > 0 else 0,
            "total_reach": w_reach,
            "total_interactions": w_interactions,
            "total_likes": w_likes,
            "avg_likes_per_post": round(w_likes / w_count, 1) if w_count > 0 else 0,
            "total_shares": w_shares,
            "avg_shares_per_post": round(w_shares / w_count, 1) if w_count > 0 else 0,
            "total_saves": w_saves,
            "avg_saves_per_post": round(w_saves / w_count, 1) if w_count > 0 else 0,
            "total_comments": w_comments,
            "avg_comments_per_post": round(w_comments / w_count, 1) if w_count > 0 else 0,
            "total_follows": w_follows,
            "engagement_rate_pct": round(w_interactions / w_views * 100, 2) if w_views > 0 else 0,
            "top_video": top_w["title"] if top_w else "-",
            "top_views": top_w["views"] if top_w else 0,
            "top_catalog_growers": catalog_growers[:3]
        }

    # Agrupamiento TEMÁTICO
    topics_list = [
        "Tecnodistopía & Geopolítica",
        "Datos Duros & Desmitificación",
        "Hábitos & Ansiedad Digital",
        "Rosca Política & Sociedad"
    ]
    topic_stats = {}
    for t in topics_list:
        t_posts = [p for p in all_posts if p["topic"] == t]
        t_count = len(t_posts)
        t_views = sum(p["views"] for p in t_posts)
        t_shares = sum(p["shares"] for p in t_posts)
        t_saves = sum(p["saves"] for p in t_posts)
        t_comms = sum(p["comments"] for p in t_posts)
        t_interactions = sum(p["interactions"] for p in t_posts)
        topic_stats[t] = {
            "topic": t,
            "count": t_count,
            "total_views": t_views,
            "avg_views": int(t_views / t_count) if t_count > 0 else 0,
            "total_shares": t_shares,
            "avg_shares": round(t_shares / t_count, 1) if t_count > 0 else 0,
            "total_saves": t_saves,
            "total_comments": t_comms,
            "total_interactions": t_interactions,
            "engagement_pct": round(t_interactions / t_views * 100, 2) if t_views > 0 else 0
        }

    total_views = sum(p["views"] for p in all_posts)
    total_interactions = sum(p["interactions"] for p in all_posts)
    total_likes = sum(p["likes"] for p in all_posts)
    total_shares = sum(p["shares"] for p in all_posts)
    total_saves = sum(p["saves"] for p in all_posts)
    total_comments = sum(p["comments"] for p in all_posts)
    total_reach = sum(p["reach"] for p in all_posts)
    total_follows = sum(p["follows"] for p in all_posts)

    # Período de fechas abarcado
    all_dates = [p["date_dt"] for p in all_posts if p.get("date_dt") and p["date_dt"] != "1970-01-01"]
    min_date_str = min(all_dates)[:10] if all_dates else ""
    max_date_str = max(all_dates)[:10] if all_dates else ""

    summary = {
        "metadata": {
            "account": "@tintaysoda.stream",
            "periodo": f"{min_date_str} al {max_date_str} (Consolidado Histórico Multimes)",
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "total_posts": len(all_posts),
            "meses_procesados": months_list,
            "fuente": "Meta Business Suite Oficial (Exportaciones Anexadas)"
        },
        "kpis": {
            "total_views": total_views,
            "total_interactions": total_interactions,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "total_saves": total_saves,
            "total_reach": total_reach,
            "total_follows": total_follows,
            "save_rate_pct": round(total_saves / total_views * 100, 2) if total_views > 0 else 0,
            "share_rate_pct": round(total_shares / total_views * 100, 2) if total_views > 0 else 0,
            "engagement_rate_pct": round(total_interactions / total_views * 100, 2) if total_views > 0 else 0,
            "top_performer": all_posts[0] if all_posts else None
        },
        "monthly_stats": monthly_stats,
        "weeks_stats": weeks_stats,
        "topic_stats": topic_stats,
        "posts": all_posts
    }

    # Guardar en archivo JSON
    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[INFO] JSON estructurado guardado en: {JSON_OUTPUT}")

    # Inyección directa y automática en dashboard.html
    if os.path.exists(HTML_OUTPUT):
        try:
            with open(HTML_OUTPUT, "r", encoding="utf-8") as f:
                html_code = f.read()

            summary_json_str = json.dumps(summary, ensure_ascii=False, indent=2)
            pattern = r"(const METRICS_SUMMARY\s*=\s*)\{[\s\S]*?\n\s*\};"
            if re.search(pattern, html_code):
                updated_html = re.sub(pattern, lambda m: m.group(1) + summary_json_str + ";", html_code, count=1)
                with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
                    f.write(updated_html)
                with open(INDEX_OUTPUT, "w", encoding="utf-8") as f:
                    f.write(updated_html)
                with open(ROOT_INDEX, "w", encoding="utf-8") as f:
                    f.write(updated_html)
                print(f"[INFO] dashboard.html, index.html y root index.html actualizados correctamente.")
            else:
                print(f"[WARN] No se encontró el marcador const METRICS_SUMMARY en dashboard.html.")
        except Exception as e:
            print(f"[WARN] Error al actualizar dashboard.html / index.html: {e}")

    return summary


if __name__ == "__main__":
    summary = process_all_exports()
    print("[EXITO] Procesamiento multimes y semanal finalizado correctamente.")
