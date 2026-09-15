"""
sync_instagram_api.py
Script de sincronización autónoma para @tintaysoda.stream con la API de Instagram Graph.
Diseñado para ejecutarse semanalmente en GitHub Actions o manualmente.
Cero dependencias externas (utiliza únicamente la librería estándar de Python: urllib, json, re, datetime, os).
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta

# Asegurar encoding UTF-8 en consola
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
METRICAS_DIR = os.path.join(BASE_DIR, "metricas")
JSON_OUTPUT = os.path.join(METRICAS_DIR, "historico_metricas.json")
RAW_JSON_OUTPUT = os.path.join(METRICAS_DIR, "historico_crudo.json")
HTML_OUTPUT = os.path.join(METRICAS_DIR, "dashboard.html")
INDEX_OUTPUT = os.path.join(METRICAS_DIR, "index.html")
ROOT_INDEX = os.path.join(BASE_DIR, "index.html")

GRAPH_API_VERSION = "v19.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

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


def assign_temporal_groups(dt_arg):
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

    if week_num >= 1:
        week_label = f"Semana {week_num} ({range_str})"
    else:
        week_label = f"Semana ({range_str})"

    return month_label, week_label



def make_api_request(url, token):
    separator = "&" if "?" in url else "?"
    full_url = f"{url}{separator}access_token={token}"
    req = urllib.request.Request(
        full_url,
        headers={"User-Agent": "TintaYSodaMetricsBot/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_instagram_media(account_id, token):
    fields = "id,caption,media_type,media_product_type,timestamp,permalink,thumbnail_url,like_count,comments_count"
    url = f"{GRAPH_BASE_URL}/{account_id}/media?fields={fields}&limit=50"
    data = make_api_request(url, token)
    return data.get("data", [])


def fetch_media_insights(media_id, media_product_type, token):
    """
    Consulta métricas privadas de reels/posts (views, reach, saved, shares).
    """
    insights = {
        "views": 0,
        "reach": 0,
        "saved": 0,
        "shares": 0
    }
    
    metric_candidates = [
        "views,reach,saved,shares",
        "reach,saved,shares,plays",
        "reach,saved,shares",
        "views,reach,saved",
        "reach,saved",
        "plays,reach"
    ]
    
    for candidate in metric_candidates:
        url = f"{GRAPH_BASE_URL}/{media_id}/insights?metric={candidate}"
        try:
            res = make_api_request(url, token)
            data_list = res.get("data", [])
            found_any = False
            for item in data_list:
                name = item.get("name")
                val = 0
                values = item.get("values", [])
                if values and "value" in values[0]:
                    val = values[0]["value"]
                elif "value" in item:
                    val = item["value"]
                
                if name in ["views", "plays", "ig_reels_video_view_total_time"]:
                    insights["views"] = max(insights["views"], int(val))
                    found_any = True
                elif name == "reach":
                    insights["reach"] = max(insights["reach"], int(val))
                    found_any = True
                elif name == "saved":
                    insights["saved"] = max(insights["saved"], int(val))
                    found_any = True
                elif name == "shares":
                    insights["shares"] = max(insights["shares"], int(val))
                    found_any = True
            if found_any:
                break
        except Exception:
            continue

    return insights


def get_last_completed_sunday(dt_now=None):
    if dt_now is None:
        # Hora actual en Argentina (UTC-3)
        dt_now = datetime.utcnow() - timedelta(hours=3)
    dt_now = dt_now.replace(year=2026)
    # Lunes=0, Martes=1, ..., Domingo=6
    # Si hoy es lunes a sábado (0..5), el domingo cerrado fue hace (weekday + 1) días.
    # Si hoy es domingo (6), el domingo en curso no terminó, el cerrado fue hace 7 días.
    days_since_sunday = (dt_now.weekday() + 1) if dt_now.weekday() != 6 else 7
    last_sunday = (dt_now - timedelta(days=days_since_sunday)).date()
    return datetime(last_sunday.year, last_sunday.month, last_sunday.day, 23, 59, 59)


def load_existing_summary():
    if os.path.exists(JSON_OUTPUT):
        try:
            with open(JSON_OUTPUT, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] No se pudo leer el JSON existente: {e}")
    return {"posts": []}


def load_existing_raw_posts():
    if os.path.exists(RAW_JSON_OUTPUT):
        try:
            with open(RAW_JSON_OUTPUT, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("posts", [])
        except Exception:
            pass
    return load_existing_summary().get("posts", [])


def recalculate_summary(all_posts, filter_closed_weeks=True):
    for p in all_posts:
        if not isinstance(p, dict):
            continue
        p.setdefault("views", 0)
        p.setdefault("reach", p.get("views", 0))
        p.setdefault("interactions", 0)
        p.setdefault("likes", 0)
        p.setdefault("comments", 0)
        p.setdefault("shares", 0)
        p.setdefault("saves", 0)
        p.setdefault("follows", 0)
        p.setdefault("title", "Publicación")
        p.setdefault("duration_str", "-")
        p.setdefault("month", "Sin fecha")
        p.setdefault("week", "Sin fecha")
        p.setdefault("topic", "Rosca Política & Sociedad")
        
        # Normalizar fecha si es 1970-01-01 o falta, extrayéndola del campo date
        if not p.get("date_dt") or p.get("date_dt") == "1970-01-01":
            date_str = p.get("date", "")
            m = re.search(r"(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})", date_str)
            if m:
                d, mo, y, h, mi = map(int, m.groups())
                p["date_dt"] = f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}"
            else:
                p["date_dt"] = "1970-01-01"

        # Reasignar mes y semana de forma dinámica con el ciclo oficial Lunes a Domingo
        if p.get("date_dt") and p.get("date_dt") != "1970-01-01":
            try:
                clean_ds = p["date_dt"][:16]
                dt_p = datetime.fromisoformat(clean_ds)
                m_lbl, w_lbl = assign_temporal_groups(dt_p)
                p["month"] = m_lbl
                p["week"] = w_lbl
            except Exception:
                pass

    # Filtrar estrictamente solo publicaciones de semanas concluidas (hasta el último domingo cerrado)
    if filter_closed_weeks:
        cutoff_dt = get_last_completed_sunday()
        cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M")
        active_posts = []
        for p in all_posts:
            ds = p.get("date_dt", "")
            if not ds or ds == "1970-01-01" or ds <= cutoff_str:
                active_posts.append(p)
        print(f"[INFO] Corte semanal aplicado: semanas concluidas hasta {cutoff_dt.strftime('%d/%m/%Y')}.")
        print(f"[INFO] Posts consolidados: {len(active_posts)} (En curso omitidos: {len(all_posts) - len(active_posts)})")
    else:
        active_posts = all_posts

    all_posts = active_posts

    all_posts.sort(key=lambda x: x.get("views", 0), reverse=True)
    for idx, p in enumerate(all_posts):
        p["rank"] = idx + 1

    detected_months = list(set(p.get("month", "Sin fecha") for p in all_posts if p.get("month") != "Sin fecha"))
    months_list = sorted(detected_months, key=get_month_sort_key)

    monthly_stats = {}
    for idx, m in enumerate(months_list):
        m_posts = [p for p in all_posts if p.get("month") == m]
        m_count = len(m_posts)
        m_views = sum(p.get("views", 0) for p in m_posts)
        m_reach = sum(p.get("reach", 0) for p in m_posts)
        m_interactions = sum(p.get("interactions", 0) for p in m_posts)
        m_shares = sum(p.get("shares", 0) for p in m_posts)
        m_saves = sum(p.get("saves", 0) for p in m_posts)
        m_comments = sum(p.get("comments", 0) for p in m_posts)
        m_likes = sum(p.get("likes", 0) for p in m_posts)
        m_follows = sum(p.get("follows", 0) for p in m_posts)

        avg_views = int(m_views / m_count) if m_count > 0 else 0
        avg_shares = round(m_shares / m_count, 1) if m_count > 0 else 0
        avg_saves = round(m_saves / m_count, 1) if m_count > 0 else 0
        avg_comments = round(m_comments / m_count, 1) if m_count > 0 else 0

        top_post = max(m_posts, key=lambda x: x.get("views", 0)) if m_posts else None

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
                "title": top_post.get("title", ""),
                "views": top_post.get("views", 0),
                "shares": top_post.get("shares", 0),
                "saves": top_post.get("saves", 0),
                "comments": top_post.get("comments", 0),
                "duration_str": top_post.get("duration_str", "-")
            } if top_post else None
        }

    def get_week_min_date(w_name):
        w_posts = [p for p in all_posts if p.get("week") == w_name]
        return min((p.get("date_dt") or "9999") for p in w_posts) if w_posts else "9999"

    detected_weeks = list(set(p.get("week", "Sin fecha") for p in all_posts if p.get("week") != "Sin fecha"))
    weeks_order = sorted(detected_weeks, key=get_week_min_date)

    weeks_stats = {}
    for w in weeks_order:
        w_posts = [p for p in all_posts if p.get("week") == w]
        w_count = len(w_posts)
        w_views = sum(p.get("views", 0) for p in w_posts)
        w_reach = sum(p.get("reach", 0) for p in w_posts)
        w_interactions = sum(p.get("interactions", 0) for p in w_posts)
        w_shares = sum(p.get("shares", 0) for p in w_posts)
        w_saves = sum(p.get("saves", 0) for p in w_posts)
        w_comments = sum(p.get("comments", 0) for p in w_posts)
        w_likes = sum(p.get("likes", 0) for p in w_posts)
        w_follows = sum(p.get("follows", 0) for p in w_posts)

        top_w = max(w_posts, key=lambda x: x.get("views", 0)) if w_posts else None

        weeks_stats[w] = {
            "week": w,
            "posts_count": w_count,
            "total_views": w_views,
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
            "top_video": top_w.get("title", "-") if top_w else "-",
            "top_views": top_w.get("views", 0) if top_w else 0
        }

    topics_list = [
        "Tecnodistopía & Geopolítica",
        "Datos Duros & Desmitificación",
        "Hábitos & Ansiedad Digital",
        "Rosca Política & Sociedad"
    ]
    topic_stats = {}
    for t in topics_list:
        t_posts = [p for p in all_posts if p.get("topic") == t]
        t_count = len(t_posts)
        t_views = sum(p.get("views", 0) for p in t_posts)
        t_shares = sum(p.get("shares", 0) for p in t_posts)
        t_saves = sum(p.get("saves", 0) for p in t_posts)
        t_comms = sum(p.get("comments", 0) for p in t_posts)
        t_interactions = sum(p.get("interactions", 0) for p in t_posts)
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

    total_views = sum(p.get("views", 0) for p in all_posts)
    total_interactions = sum(p.get("interactions", 0) for p in all_posts)
    total_likes = sum(p.get("likes", 0) for p in all_posts)
    total_shares = sum(p.get("shares", 0) for p in all_posts)
    total_saves = sum(p.get("saves", 0) for p in all_posts)
    total_comments = sum(p.get("comments", 0) for p in all_posts)
    total_reach = sum(p.get("reach", 0) for p in all_posts)
    total_follows = sum(p.get("follows", 0) for p in all_posts)

    all_dates = [p.get("date_dt", "") for p in all_posts if p.get("date_dt") and p.get("date_dt") != "1970-01-01"]
    min_date_str = min(all_dates)[:10] if all_dates else ""
    max_date_str = max(all_dates)[:10] if all_dates else ""

    summary = {
        "metadata": {
            "account": "@tintaysoda.stream",
            "periodo": f"{min_date_str} al {max_date_str} (Consolidado Histórico Multimes)",
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "total_posts": len(all_posts),
            "meses_procesados": months_list,
            "fuente": "Meta Graph API Oficial & Exportaciones Anexadas"
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

    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

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
                print(f"[INFO] dashboard.html, index.html y root index.html actualizados con éxito.")
        except Exception as e:
            print(f"[WARN] Error al actualizar HTMLs: {e}")

    return summary


def sync():
    print("========================================================")
    print("   SINCRONIZADOR AUTOMÁTICO DE MÉTRICAS (INSTAGRAM API)")
    print("   Canal: @tintaysoda.stream")
    print("========================================================")

    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    account_id = os.environ.get("IG_ACCOUNT_ID", "").strip()

    if not token or not account_id:
        print("[AVISO] No se encontraron las variables IG_ACCESS_TOKEN y/o IG_ACCOUNT_ID.")
        return

    print(f"[INFO] Conectando a Meta Graph API para la cuenta ID: {account_id}...")
    try:
        media_items = fetch_instagram_media(account_id, token)
        print(f"[INFO] Se obtuvieron {len(media_items)} publicaciones recientes desde la API.")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"[ERROR] Error al consultar Meta Graph API (HTTP {e.code}): {error_body}")
        return
    except Exception as e:
        print(f"[ERROR] Error inesperado al conectar con Meta API: {e}")
        return

    existing_posts = load_existing_raw_posts()
    posts_by_id = {str(p["post_id"]): p for p in existing_posts if isinstance(p, dict) and "post_id" in p}

    nuevos_posts_count = 0
    actualizados_posts_count = 0

    for item in media_items:
        media_id = str(item.get("id"))
        caption = item.get("caption", "")
        clean_title = ""
        for line in caption.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                clean_title = line
                break
        if not clean_title:
            clean_title = f"Publicación #{media_id[-6:]}"

        timestamp_str = item.get("timestamp", "")
        dt_arg = None
        date_display = timestamp_str
        date_dt_str = "1970-01-01"
        if timestamp_str:
            try:
                clean_ts = timestamp_str.replace("Z", "+00:00")
                dt_utc = datetime.fromisoformat(clean_ts)
                dt_arg = dt_utc - timedelta(hours=3)
                dt_arg_norm = dt_arg.replace(year=2026)
                date_display = dt_arg_norm.strftime("%d/%m/%Y %H:%M hs")
                date_dt_str = dt_arg_norm.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        month_label, week_label = assign_temporal_groups(dt_arg)
        topic = classify_topic(clean_title, caption)
        media_type = item.get("media_type", "VIDEO")
        media_product_type = item.get("media_product_type", "REELS")
        clean_type = "Reel" if media_product_type == "REELS" or media_type == "VIDEO" else "Carrusel"
        permalink = item.get("permalink", "")
        likes = int(item.get("like_count", 0))
        comments = int(item.get("comments_count", 0))

        # Consultar métricas privadas oficiales (insights)
        insights = fetch_media_insights(media_id, media_product_type, token)
        views = insights["views"] if insights["views"] > 0 else (likes + comments)
        reach = insights["reach"] if insights["reach"] > 0 else views
        saved = insights["saved"]
        shares = insights["shares"]

        interactions = likes + comments + shares + saved
        save_rate = round((saved / views * 100), 2) if views > 0 else 0
        share_rate = round((shares / views * 100), 2) if views > 0 else 0
        engagement_rate = round((interactions / views * 100), 2) if views > 0 else 0

        post_obj = {
            "post_id": media_id,
            "title": clean_title,
            "full_text": caption,
            "date": date_display,
            "date_dt": date_dt_str,
            "month": month_label,
            "week": week_label,
            "topic": topic,
            "type": clean_type,
            "permalink": permalink,
            "duration_sec": 0,
            "duration_str": "-",
            "views": views,
            "reach": reach,
            "interactions": interactions,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "saves": saved,
            "follows": 0,
            "save_rate_pct": save_rate,
            "share_rate_pct": share_rate,
            "engagement_rate_pct": engagement_rate
        }

        print(f"[POST] ID={media_id} | {week_label} | Views={views} | Reach={reach} | Likes={likes} | Shares={shares} | {clean_title[:30]}...")

        if media_id in posts_by_id:
            prev_post = posts_by_id[media_id]
            post_obj["duration_str"] = prev_post.get("duration_str", "-")
            post_obj["duration_sec"] = prev_post.get("duration_sec", 0)
            post_obj["follows"] = prev_post.get("follows", 0)
            if views > prev_post.get("views", 0) or interactions > prev_post.get("interactions", 0) or prev_post.get("views", 0) == 0:
                posts_by_id[media_id] = post_obj
                actualizados_posts_count += 1
        else:
            posts_by_id[media_id] = post_obj
            nuevos_posts_count += 1

    all_raw_posts = list(posts_by_id.values())
    try:
        with open(RAW_JSON_OUTPUT, "w", encoding="utf-8") as f:
            json.dump({"posts": all_raw_posts}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] No se pudo guardar el pool crudo: {e}")

    summary = recalculate_summary(all_raw_posts, filter_closed_weeks=True)

    print(f"[OK] Sincronización completada:")
    print(f"     - Nuevos posts agregados: {nuevos_posts_count}")
    print(f"     - Posts actualizados con métricas más recientes: {actualizados_posts_count}")
    print(f"     - Total de publicaciones en el dashboard: {len(all_posts)}")
    print(f"     - Total visualizaciones acumuladas: {summary['kpis']['total_views']:,}")


if __name__ == "__main__":
    sync()
