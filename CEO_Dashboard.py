"""
CEO 指挥舱模块：从 yfinance 获取 CEO 信息，从 NewsAPI 获取相关新闻，极简 UI 展示。
云端密钥：在 Streamlit Community Cloud → App settings → Secrets 中配置 NEWS_API_KEY。
本地：可设置环境变量 NEWS_API_KEY，或使用 .streamlit/secrets.toml（勿提交到 Git）。
"""
import os

import streamlit as st
import yfinance as yf
import requests
from datetime import datetime
from typing import Optional


def _news_api_key() -> str:
    env = (os.environ.get("NEWS_API_KEY") or "").strip()
    if env:
        return env
    try:
        return str(st.secrets["NEWS_API_KEY"]).strip()
    except Exception:
        return ""


def get_ceo_news(ceo_name: str) -> list:
    """
    使用 NewsAPI 搜索与 CEO 姓名相关的新闻，最多返回 5 条。
    若未配置密钥、请求失败或解析异常，直接返回空列表，不抛错、不卡死。
    """
    if not ceo_name or not ceo_name.strip():
        return []
    api_key = _news_api_key()
    if not api_key:
        return []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": ceo_name.strip(),
            "apiKey": api_key,
            "pageSize": 5,
            "language": "en",
            "sortBy": "publishedAt",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "ok":
            return []
        articles = data.get("articles") or []
        out = []
        for a in articles[:5]:
            title = (a.get("title") or "").strip()
            link = (a.get("url") or "").strip()
            pub = a.get("publishedAt") or ""
            if title or link:
                out.append({"title": title or "(无标题)", "url": link, "publishedAt": pub})
        return out
    except Exception:
        return []


def _get_ceo_from_officers(company_officers: list) -> Optional[dict]:
    """从 companyOfficers 中找出 CEO，返回包含 name, title, age 的字典。"""
    if not company_officers:
        return None
    ceo_keywords = ("ceo", "chief executive officer", "chief executive")
    for o in company_officers:
        if not isinstance(o, dict):
            continue
        title = (o.get("title") or "").strip().lower()
        if any(k in title for k in ceo_keywords):
            name = (o.get("name") or "").strip() or "—"
            year_born = o.get("yearBorn")
            age = None
            if isinstance(year_born, (int, float)) and year_born > 1900:
                age = datetime.now().year - int(year_born)
            return {
                "name": name,
                "title": (o.get("title") or "").strip() or "—",
                "age": age,
            }
    return None


def render_ceo_dashboard(ticker_symbol: str, info: Optional[dict] = None):
    """
    渲染 CEO 指挥舱极简 UI：
    顶部 CEO 基础信息卡片，下方 5 条新闻（带链接），文本框展示 officerSummary。
    info 可选；若不传则根据 ticker_symbol 用 yfinance 拉取。
    """
    st.subheader("CEO 指挥舱")
    if info is None:
        try:
            t = yf.Ticker(ticker_symbol)
            info = t.info or {}
        except Exception:
            info = {}

    officers = info.get("companyOfficers")
    if isinstance(officers, list):
        ceo = _get_ceo_from_officers(officers)
    else:
        ceo = None

    # ——— 顶部：CEO 基础信息卡片 ———
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("姓名", ceo.get("name", "—") if ceo else "—")
    with col2:
        st.metric("职位", ceo.get("title", "—") if ceo else "—")
    with col3:
        age_val = ceo.get("age") if ceo else None
        st.metric("年龄", f"{age_val} 岁" if age_val is not None else "—")

    # ——— 新闻列表（最多 5 条，带链接） ———
    st.markdown("**相关新闻**")
    ceo_name = (ceo or {}).get("name") or ""
    news_list = get_ceo_news(ceo_name) if ceo_name and ceo_name != "—" else []
    if not news_list:
        st.caption("暂无新闻（请在 Secrets / 环境变量中配置 NEWS_API_KEY，或当前无相关报道）")
    else:
        for i, n in enumerate(news_list, 1):
            title, url, pub = n.get("title", ""), n.get("url", ""), n.get("publishedAt", "")
            if url:
                st.markdown(f"{i}. [{title}]({url})")
            else:
                st.markdown(f"{i}. {title}")
            if pub:
                st.caption(pub[:10] if len(pub) >= 10 else pub)

    # ——— officerSummary 文本框 ———
    st.markdown("**高管摘要（officerSummary）**")
    summary = info.get("officerSummary") or info.get("longBusinessSummary") or ""
    if summary:
        st.text_area("", value=summary, height=200, disabled=True, label_visibility="collapsed")
    else:
        st.caption("暂无高管摘要内容。")
