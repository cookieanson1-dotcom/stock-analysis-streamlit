import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

try:
    from prophet import Prophet
except Exception:
    # 兼容旧包名 fbprophet
    try:
        from fbprophet import Prophet  # type: ignore
    except Exception:
        Prophet = None  # 延迟在界面中提示用户安装

from CEO_Dashboard import render_ceo_dashboard


st.set_page_config(
    page_title="智能股票分析系统",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_history(ticker: str, days: int) -> pd.DataFrame:
    end = datetime.today()
    start = end - timedelta(days=days + 7)  # 多取几天，方便 Prophet 训练
    data = yf.download(ticker, start=start, end=end)
    if data is None or data.empty:
        raise ValueError("未能获取到该股票的历史数据，请检查代码是否正确。")
    # 处理可能出现的多层索引（MultiIndex）表头
    if isinstance(data.columns, pd.MultiIndex):
        try:
            # 优先按照用户建议，直接在列层级上降维
            data.columns = data.columns.droplevel(1)
        except Exception:
            # 兜底方案：完全拉平成一维索引
            data.columns = data.columns.to_flat_index()
    data = data.reset_index()
    # 确保日期列为纯日期（无时区、无时间部分），方便 Prophet 使用
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"]).dt.tz_localize(None).dt.normalize()
    return data


@st.cache_data(show_spinner=False)
def load_ticker_info(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info
    if not info:
        raise ValueError("未能获取到该股票的基本面信息。")
    return info


@st.cache_resource(show_spinner=False)
def train_prophet_model(history_df: pd.DataFrame):
    if Prophet is None:
        raise ImportError(
            "未检测到 Prophet / fbprophet，请先在终端执行：pip install prophet 或 pip install fbprophet"
        )
    # 再次防御性处理列名，避免 MultiIndex 传入 Prophet
    df = history_df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df.columns = df.columns.droplevel(1)
        except Exception:
            df.columns = df.columns.to_flat_index()

    df = df[["Date", "Close"]].rename(columns={"Date": "ds", "Close": "y"})
    # Prophet 期望 ds 为日期/时间序列，这里统一成“纯日期”格式
    df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None).dt.normalize()
    model = Prophet(daily_seasonality=True)
    model.fit(df)
    return model


def render_overview_tab(ticker_symbol: str):
    st.subheader("📊 概览与基本面")
    try:
        info = load_ticker_info(ticker_symbol)
    except Exception as e:
        st.error(f"获取基本面信息失败：{e}")
        return

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    previous_close = info.get("previousClose")
    market_cap = info.get("marketCap")
    pe_ratio = info.get("trailingPE") or info.get("forwardPE")
    dividend_yield = info.get("dividendYield")

    if current_price is not None and previous_close not in (None, 0):
        change_pct = (current_price - previous_close) / previous_close * 100
    else:
        change_pct = None

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("当前股价", f"{current_price:.2f}" if current_price is not None else "—")

    with col2:
        if change_pct is not None:
            delta_str = f"{change_pct:+.2f}%"
            delta_color = "normal"
            st.metric("今日涨跌幅", delta_str, delta_color=delta_color)
        else:
            st.metric("今日涨跌幅", "—")

    def format_market_cap(mc):
        if mc is None:
            return "—"
        if mc >= 1e12:
            return f"{mc/1e12:.2f} 万亿"
        if mc >= 1e8:
            return f"{mc/1e8:.2f} 亿"
        if mc >= 1e4:
            return f"{mc/1e4:.2f} 万"
        return str(mc)

    with col3:
        st.metric("市值", format_market_cap(market_cap))

    with col4:
        st.metric("市盈率 (PE)", f"{pe_ratio:.2f}" if pe_ratio is not None else "—")

    with col5:
        if dividend_yield is not None:
            st.metric("股息率", f"{dividend_yield * 100:.2f}%")
        else:
            st.metric("股息率", "—")

    st.markdown("---")

    # 公司简介（尝试提取中文信息）
    long_name = info.get("longName") or info.get("shortName") or ticker_symbol
    country = info.get("country", "—")
    industry = info.get("industry") or info.get("sector") or "—"
    city = info.get("city")
    state = info.get("state")
    address = ", ".join([x for x in [city, state, country] if x])
    employees = info.get("fullTimeEmployees")

    st.markdown(f"### 公司概况：{long_name}")

    desc = info.get("longBusinessSummary") or ""
    zh_desc = desc
    # 简单启发：若包含中文字符，则优先展示中文部分
    if any("\u4e00" <= ch <= "\u9fff" for ch in desc):
        zh_desc = desc
    else:
        # 对英文简介进行非常简要的“提取”：截取前 3-4 句
        parts = desc.split(". ")
        zh_desc = ". ".join(parts[:3]).strip()

    if zh_desc:
        st.write(zh_desc)
    else:
        st.info("暂无公司简介信息。")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.write("**行业 / 板块：**")
        st.write(industry)
    with col_b:
        st.write("**总部地点：**")
        st.write(address if address else "—")
    with col_c:
        st.write("**员工人数：**")
        st.write(f"{employees:,}" if isinstance(employees, int) else "—")


def render_market_tab(ticker_symbol: str):
    st.subheader("📈 深度行情查询")

    days = st.slider("选择回溯天数（自然日）", min_value=30, max_value=730, value=180, step=10)
    metric = st.selectbox(
        "选择要查看的指标",
        ("收盘价", "成交量", "日内高低价波幅"),
        index=0,
    )

    try:
        df = load_history(ticker_symbol, days)
    except Exception as e:
        st.error(f"获取历史行情失败：{e}")
        return

    if df.empty:
        st.warning("未获取到任何历史行情数据。")
        return

    fig = go.Figure()

    if metric == "收盘价":
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["Close"],
                mode="lines",
                name="收盘价",
                line=dict(color="#1f77b4"),
            )
        )
        fig.update_layout(yaxis_title="价格", hovermode="x unified")
    elif metric == "成交量":
        fig.add_trace(
            go.Bar(
                x=df["Date"],
                y=df["Volume"],
                name="成交量",
                marker_color="#ff7f0e",
            )
        )
        fig.update_layout(yaxis_title="成交量", hovermode="x unified")
    else:  # 日内高低价波幅
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["High"],
                mode="lines",
                name="最高价",
                line=dict(color="#d62728"),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["Low"],
                mode="lines",
                name="最低价",
                line=dict(color="#2ca02c"),
                fill="tonexty",
                fillcolor="rgba(31, 119, 180, 0.1)",
            )
        )
        fig.update_layout(yaxis_title="价格区间", hovermode="x unified")

    fig.update_layout(
        xaxis_title="日期",
        legend_title_text="指标",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    fig.update_xaxes(rangeslider_visible=True)

    st.plotly_chart(fig, use_container_width=True)


def render_ai_tab(ticker_symbol: str):
    st.subheader("🤖 AI 趋势预测（Prophet）")

    forecast_days = st.slider("选择预测天数", min_value=7, max_value=365, value=60, step=1)

    try:
        df = load_history(ticker_symbol, 730)
    except Exception as e:
        st.error(f"获取历史数据失败，无法进行预测：{e}")
        return

    if df.empty:
        st.warning("历史数据为空，无法进行预测。")
        return

    try:
        model = train_prophet_model(df)
    except ImportError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"训练预测模型失败：{e}")
        return

    future = model.make_future_dataframe(periods=forecast_days)
    forecast = model.predict(future)

    # 与训练阶段保持一致的日期格式 & 列名
    hist = df.copy()
    if isinstance(hist.columns, pd.MultiIndex):
        try:
            hist.columns = hist.columns.droplevel(1)
        except Exception:
            hist.columns = hist.columns.to_flat_index()

    hist = hist[["Date", "Close"]].rename(columns={"Date": "ds", "Close": "y"})
    hist["ds"] = pd.to_datetime(hist["ds"]).dt.tz_localize(None).dt.normalize()
    merged = pd.merge(
        forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]],
        hist,
        on="ds",
        how="left",
    )

    fig = go.Figure()

    # 历史价格
    fig.add_trace(
        go.Scatter(
            x=merged["ds"],
            y=merged["y"],
            mode="lines",
            name="历史收盘价",
            line=dict(color="#1f77b4"),
        )
    )

    # 预测中位线
    fig.add_trace(
        go.Scatter(
            x=merged["ds"],
            y=merged["yhat"],
            mode="lines",
            name="预测价格（中位线）",
            line=dict(color="#d62728", dash="dash"),
        )
    )

    # 风险波动区间（上下界填充）
    fig.add_trace(
        go.Scatter(
            x=merged["ds"],
            y=merged["yhat_upper"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=merged["ds"],
            y=merged["yhat_lower"],
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(255, 127, 14, 0.2)",
            line=dict(width=0),
            name="预测区间",
        )
    )

    fig.update_layout(
        xaxis_title="日期",
        yaxis_title="价格",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=40, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)

    # 仅导出预测区间内的明细
    forecast_part = forecast.tail(forecast_days)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    forecast_part = forecast_part.rename(
        columns={
            "ds": "日期",
            "yhat": "预测价格",
            "yhat_lower": "预测下界",
            "yhat_upper": "预测上界",
        }
    )

    csv = forecast_part.to_csv(index=False).encode("utf-8-sig")
    filename = f"{ticker_symbol.replace('.', '_')}_prophet_forecast.csv"

    st.download_button(
        label="📥 下载预测明细（CSV）",
        data=csv,
        file_name=filename,
        mime="text/csv",
    )


def main():
    st.title("📈 智能股票分析系统（Python / Streamlit）")

    with st.sidebar:
        st.header("全局配置")
        ticker_symbol = st.text_input(
            "请输入股票代码（支持美股 / 港股 / A股，例如 NVDA, 0700.HK, 600519.SS）",
            value="NVDA",
        ).strip()

        st.markdown("---")
        menu = st.radio(
            "功能导航",
            options=["概览与基本面", "深度行情查询", "AI 趋势预测", "CEO 指挥舱"],
            index=0,
        )

    if not ticker_symbol:
        st.warning("请输入有效的股票代码。")
        return

    # 顶部统一错误保护：若 yfinance 请求失败，内部各模块会单独处理异常
    if menu == "概览与基本面":
        try:
            render_overview_tab(ticker_symbol)
        except Exception as e:
            st.error(f"加载概览与基本面模块时出现问题：{e}")
    elif menu == "深度行情查询":
        try:
            render_market_tab(ticker_symbol)
        except Exception as e:
            st.error(f"加载深度行情模块时出现问题：{e}")
    elif menu == "CEO 指挥舱":
        try:
            render_ceo_dashboard(ticker_symbol)
        except Exception as e:
            st.error(f"加载 CEO 指挥舱时出现问题：{e}")
    else:
        try:
            render_ai_tab(ticker_symbol)
        except Exception as e:
            st.error(f"加载 AI 趋势预测模块时出现问题：{e}")

    st.markdown("---")
    st.caption(
        "提示：若出现网络超时或数据获取失败，请稍后重试，或检查本地网络 / 代理配置。"
    )


if __name__ == "__main__":
    main()
