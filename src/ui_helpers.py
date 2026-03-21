"""
Shared UI helper components for BotForex Streamlit app.
Reusable: section headers, info cards, status badges, metric rows, alert boxes.

All user-facing text uses t() for i18n (Vietnamese default).

Translation keys used / suggested:
    status_running   → "Đang chạy"
    status_stopped   → "Đã dừng"
    status_waiting   → "Đang chờ"
    status_error     → "Lỗi"
    status_success   → "Thành công"
    status_live      → "Live"
    status_test      → "Test"
    badge_unknown    → "Không rõ"
"""

import streamlit as st
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Status label map — Vietnamese first, fallback via i18n if available
# ---------------------------------------------------------------------------
_STATUS_LABEL_VI: dict[str, str] = {
    "running":  "Đang chạy",
    "stopped":  "Đã dừng",
    "waiting":  "Đang chờ",
    "error":    "Lỗi",
    "success":  "Thành công",
    "live":     "Live",
    "test":     "Test",
    "active":   "Hoạt động",
    "inactive": "Không hoạt động",
    "pending":  "Đang xử lý",
}

_STATUS_CSS_CLASS: dict[str, str] = {
    "running":  "bf-badge-running",
    "stopped":  "bf-badge-stopped",
    "waiting":  "bf-badge-waiting",
    "error":    "bf-badge-error",
    "success":  "bf-badge-success",
    "live":     "bf-badge-live",
    "test":     "bf-badge-test",
    "active":   "bf-badge-running",
    "inactive": "bf-badge-stopped",
    "pending":  "bf-badge-waiting",
}

_COLOR_MAP: dict[str, str] = {
    "blue":  "bf-card-blue",
    "green": "bf-card-green",
    "amber": "bf-card-amber",
    "red":   "bf-card-red",
}

_INFO_CARD_COLOR_MAP: dict[str, str] = {
    "blue":  "bf-info-card-blue",
    "green": "bf-info-card-green",
    "amber": "bf-info-card-amber",
    "red":   "bf-info-card-red",
}

_ALERT_ICONS: dict[str, str] = {
    "info":    "ℹ️",
    "success": "✅",
    "warning": "⚠️",
    "error":   "❌",
}

_ALERT_CSS: dict[str, str] = {
    "info":    "bf-alert-info",
    "success": "bf-alert-success",
    "warning": "bf-alert-warning",
    "error":   "bf-alert-error",
}


# ---------------------------------------------------------------------------
# section_header
# ---------------------------------------------------------------------------
def section_header(
    title: str,
    icon: str = "",
    description: str = "",
) -> None:
    """
    Render a styled section header with optional icon and description.

    Args:
        title:       Section title (use t() before passing, or raw Vietnamese).
        icon:        Emoji/icon prefix shown left of title.
        description: Optional subtitle shown below title in muted text.

    Example:
        section_header(t("page_bots"), "🤖", "Quản lý và theo dõi các bot giao dịch")
    """
    icon_html = f'<span class="bf-section-icon">{icon}</span>' if icon else ""
    desc_html = (
        f'<div class="bf-section-desc">{description}</div>' if description else ""
    )
    html = f"""
<div class="bf-section-header">
    {icon_html}
    <div>
        <div class="bf-section-title">{title}</div>
        {desc_html}
    </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# status_badge
# ---------------------------------------------------------------------------
def status_badge(status: str, label: Optional[str] = None) -> str:
    """
    Return the HTML string for a colored status badge.
    Render it with: st.markdown(status_badge("running"), unsafe_allow_html=True)

    Args:
        status: One of 'running', 'stopped', 'waiting', 'error', 'success',
                'live', 'test', 'active', 'inactive', 'pending'
        label:  Override display label (Vietnamese). Defaults to built-in map.

    Returns:
        HTML string for the badge.
    """
    key = status.lower().strip()
    css_class = _STATUS_CSS_CLASS.get(key, "bf-badge-info")
    display_label = label or _STATUS_LABEL_VI.get(key, status.upper())
    return f'<span class="bf-badge {css_class}">{display_label}</span>'


# ---------------------------------------------------------------------------
# info_card
# ---------------------------------------------------------------------------
def info_card(
    title: str,
    value: str,
    icon: str = "",
    delta: str = "",
    color: str = "blue",
) -> None:
    """
    Render a styled info/metric card using HTML.

    Args:
        title:  Card label (e.g. t("balance") → "Số dư").
        value:  Main display value (e.g. "$12,500").
        icon:   Emoji icon shown above value.
        delta:  Optional delta string; prefix '+'/'-' drives color.
                e.g. "+5.2%" (green), "-1.3%" (red), "0" (neutral).
        color:  Top-border color: 'blue' | 'green' | 'amber' | 'red'.

    Example:
        info_card(t("balance"), "$12,500", "💰", "+2.3%", "green")
    """
    color_class = _INFO_CARD_COLOR_MAP.get(color, "bf-info-card-blue")
    icon_html = f'<span class="bf-info-card-icon">{icon}</span>' if icon else ""

    delta_html = ""
    if delta:
        d = str(delta).strip()
        if d.startswith("+"):
            delta_class = "positive"
            delta_icon = "▲ "
        elif d.startswith("-"):
            delta_class = "negative"
            delta_icon = "▼ "
        else:
            delta_class = "neutral"
            delta_icon = ""
        delta_html = (
            f'<div class="bf-info-card-delta {delta_class}">'
            f"{delta_icon}{d}</div>"
        )

    html = f"""
<div class="bf-info-card {color_class}">
    {icon_html}
    <div class="bf-info-card-label">{title}</div>
    <div class="bf-info-card-value">{value}</div>
    {delta_html}
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# metric_row
# ---------------------------------------------------------------------------
def metric_row(metrics: list[dict]) -> None:
    """
    Render a horizontal row of info/metric cards.

    Each dict in the list supports:
        label (str, required)   — card title (Vietnamese / use t())
        value (str, required)   — main value
        icon  (str, optional)   — emoji icon
        delta (str, optional)   — delta string ('+'/'-' prefix for color)
        color (str, optional)   — 'blue'|'green'|'amber'|'red' (default 'blue')

    Example:
        metric_row([
            {"label": t("balance"),  "value": "$12,500", "icon": "💰", "delta": "+2.3%", "color": "green"},
            {"label": t("win_rate"), "value": "68%",     "icon": "🏆", "delta": "+1.2%", "color": "blue"},
            {"label": t("profit"),   "value": "+$430",   "icon": "📈", "delta": "+$30",  "color": "green"},
            {"label": t("losses"),   "value": "12",      "icon": "📉", "delta": "-2",    "color": "red"},
        ])
    """
    if not metrics:
        return
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            info_card(
                title=m.get("label", ""),
                value=str(m.get("value", "")),
                icon=m.get("icon", ""),
                delta=str(m.get("delta", "")),
                color=m.get("color", "blue"),
            )


# ---------------------------------------------------------------------------
# card_container
# ---------------------------------------------------------------------------
def card_container(
    content_func: Callable,
    title: str = "",
    border_color: str = "",
) -> None:
    """
    Wrap Streamlit content in a styled card container (HTML + st.container).

    Args:
        content_func: A callable (no args) that renders Streamlit components inside.
        title:        Optional card title displayed at the top.
        border_color: Optional left-accent color: 'blue'|'green'|'amber'|'red'.

    Example:
        def my_content():
            st.write("Nội dung bên trong thẻ")
            st.metric("Lợi nhuận", "+$200")

        card_container(my_content, title="Tóm tắt giao dịch", border_color="green")
    """
    accent_class = _COLOR_MAP.get(border_color, "")
    # Opening card div
    title_html = (
        f'<div style="font-weight:600;font-size:0.95rem;'
        f'color:var(--color-text);margin-bottom:0.6rem;">{title}</div>'
        if title
        else ""
    )
    st.markdown(
        f'<div class="bf-card {accent_class}">{title_html}',
        unsafe_allow_html=True,
    )
    # Render content inside the same st container
    with st.container():
        content_func()
    # Close card div
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# alert_box
# ---------------------------------------------------------------------------
def alert_box(message: str, type: str = "info") -> None:
    """
    Render a custom-styled alert box (info/success/warning/error).
    Provides consistent styling beyond Streamlit's default st.info/st.warning.

    Args:
        message: Alert message text (Vietnamese / use t()).
        type:    'info' | 'success' | 'warning' | 'error'

    Example:
        alert_box("Kết nối MT5 thành công!", "success")
        alert_box("Chưa cấu hình tài khoản MT5.", "warning")
        alert_box("Bot đang chạy và theo dõi thị trường.", "info")
        alert_box("Lỗi kết nối: không tìm thấy server.", "error")
    """
    key = type.lower().strip()
    css_class = _ALERT_CSS.get(key, "bf-alert-info")
    icon = _ALERT_ICONS.get(key, "ℹ️")
    html = f"""
<div class="bf-alert {css_class}">
    <span class="bf-alert-icon">{icon}</span>
    <span>{message}</span>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# page_header  (bonus helper — full page title block)
# ---------------------------------------------------------------------------
def page_header(
    title: str,
    icon: str = "",
    subtitle: str = "",
    badge_status: str = "",
) -> None:
    """
    Render a full page title block with optional icon, subtitle, and status badge.

    Args:
        title:        Page title (Vietnamese / use t()).
        icon:         Emoji for the page.
        subtitle:     Short description shown below title.
        badge_status: Optional status badge ('running'|'stopped'|etc.).

    Example:
        page_header(t("page_bots"), "🤖", "Quản lý và theo dõi các bot giao dịch", "running")
    """
    badge_html = ""
    if badge_status:
        badge_html = (
            f'&nbsp;&nbsp;{status_badge(badge_status)}'
        )
    icon_html = f"{icon} " if icon else ""
    subtitle_html = (
        f'<p style="color:var(--color-text-muted);font-size:0.88rem;'
        f'margin-top:0.15rem;margin-bottom:0;">{subtitle}</p>'
        if subtitle
        else ""
    )
    html = f"""
<div style="margin-bottom:0.75rem;">
    <h1 style="margin:0;font-size:1.6rem;font-weight:700;
               color:var(--color-text);display:inline;">
        {icon_html}{title}
    </h1>
    {badge_html}
    {subtitle_html}
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# bot_status_card  (bonus — common pattern across pages)
# ---------------------------------------------------------------------------
def bot_status_card(
    bot_name: str,
    symbol: str,
    mode: str,
    status: str,
    pnl: str = "",
    extra_info: str = "",
) -> None:
    """
    Render a compact bot status card.

    Args:
        bot_name:   Bot identifier string.
        symbol:     Trading symbol (e.g. "XAUUSD").
        mode:       'live' | 'test'.
        status:     'running' | 'stopped' | 'waiting' | 'error'.
        pnl:        Optional P&L string (e.g. "+$42.00").
        extra_info: Optional extra text line (e.g. entry time).

    Example:
        bot_status_card("Bot #1", "XAUUSD", "live", "running", "+$42.00", "21:05 HCM")
    """
    accent = _COLOR_MAP.get(
        "green" if status == "running" else
        "red" if status in ("stopped", "error") else
        "amber",
        "",
    )
    mode_badge = status_badge(mode)
    stat_badge = status_badge(status)
    pnl_color = (
        "var(--color-success)" if pnl.startswith("+") else
        "var(--color-danger)" if pnl.startswith("-") else
        "var(--color-text-dim)"
    )
    pnl_html = (
        f'<span style="font-weight:700;color:{pnl_color};font-size:1rem;">{pnl}</span>'
        if pnl else ""
    )
    extra_html = (
        f'<div style="font-size:0.78rem;color:var(--color-text-muted);margin-top:0.2rem;">'
        f'{extra_info}</div>'
        if extra_info else ""
    )
    html = f"""
<div class="bf-card {accent}">
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
            <div style="font-weight:700;font-size:0.95rem;color:var(--color-text);">
                {bot_name}
                <span style="font-size:0.8rem;font-weight:400;
                             color:var(--color-text-dim);margin-left:0.4rem;">
                    {symbol}
                </span>
            </div>
            <div style="margin-top:0.3rem;display:flex;gap:0.4rem;align-items:center;">
                {mode_badge}&nbsp;{stat_badge}
            </div>
            {extra_html}
        </div>
        <div style="text-align:right;">
            {pnl_html}
        </div>
    </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)
