"""
Simple i18n module — English / Vietnamese translations for the full app.
Usage:
    from src.i18n import t, lang_toggle_button
    t("run_backtest")
"""
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# TRANSLATIONS
# ─────────────────────────────────────────────────────────────────────────────
TRANSLATIONS = {

    # ── Language toggle ──
    "lang_btn_to_vi": {"en": "🇻🇳 Tiếng Việt", "vi": "🇬🇧 English"},

    # ── Common ──
    "current_time":         {"en": "Current Time",          "vi": "Thời gian hiện tại"},
    "go_settings":          {"en": "Go to Settings",        "vi": "Đến Cài đặt"},
    "go_strategies":        {"en": "Go to Strategies",      "vi": "Đến Chiến lược"},
    "refresh":              {"en": "Refresh",               "vi": "Làm mới"},
    "symbol":               {"en": "Symbol",                "vi": "Cặp tiền"},
    "strategy":             {"en": "Strategy",              "vi": "Chiến lược"},
    "timeframe":            {"en": "Timeframe",             "vi": "Khung TG"},
    "entry_time":           {"en": "Entry Time",            "vi": "Giờ vào lệnh"},
    "window_start":         {"en": "Window Start",          "vi": "Giờ bắt đầu"},
    "window_end":           {"en": "Window End",            "vi": "Giờ kết thúc"},
    "priority_direction":   {"en": "Priority Direction",    "vi": "Hướng ưu tiên"},
    "priority_auto":        {"en": "Auto (first candle)",   "vi": "Tự động (nến đầu tiên)"},
    "priority_buy":         {"en": "BUY only",              "vi": "Chỉ MUA"},
    "priority_sell":        {"en": "SELL only",             "vi": "Chỉ BÁN"},
    "start_date":           {"en": "Start Date",            "vi": "Ngày bắt đầu"},
    "end_date":             {"en": "End Date",              "vi": "Ngày kết thúc"},
    "direction":            {"en": "Direction",             "vi": "Chiều"},
    "volume":               {"en": "Volume (Lot)",          "vi": "Khối lượng (Lot)"},
    "entry":                {"en": "Entry",                 "vi": "Giá vào"},
    "sl":                   {"en": "SL",                    "vi": "Cắt lỗ"},
    "tp":                   {"en": "TP",                    "vi": "Chốt lời"},
    "save":                 {"en": "Save",                  "vi": "Lưu"},
    "delete":               {"en": "Delete",                "vi": "Xóa"},
    "cancel":               {"en": "Cancel",                "vi": "Hủy"},
    "enabled":              {"en": "Enabled",               "vi": "Đang bật"},
    "disabled":             {"en": "Disabled",              "vi": "Đang tắt"},
    "yes":                  {"en": "Yes",                   "vi": "Có"},
    "no":                   {"en": "No",                    "vi": "Không"},
    "mode":                 {"en": "Mode",                  "vi": "Chế độ"},
    "all":                  {"en": "All",                   "vi": "Tất cả"},
    "no_data":              {"en": "No data",               "vi": "Không có dữ liệu"},
    "not_set":              {"en": "Not set",               "vi": "Chưa đặt"},
    "version":              {"en": "Version",               "vi": "Phiên bản"},
    "author":               {"en": "Author",                "vi": "Tác giả"},
    "name":                 {"en": "Name",                  "vi": "Tên"},
    "description":          {"en": "Description",           "vi": "Mô tả"},
    "created":              {"en": "Created",               "vi": "Ngày tạo"},
    "username":             {"en": "Username",              "vi": "Tên đăng nhập"},
    "password":             {"en": "Password",              "vi": "Mật khẩu"},
    "email":                {"en": "Email",                 "vi": "Email"},
    "role":                 {"en": "Role",                  "vi": "Vai trò"},
    "profit":               {"en": "Profit",                "vi": "Lợi nhuận"},
    "loss":                 {"en": "Loss",                  "vi": "Lỗ"},
    "balance":              {"en": "Balance",               "vi": "Số dư"},
    "equity":               {"en": "Equity",                "vi": "Vốn thực"},
    "ticket":               {"en": "Ticket",                "vi": "Ticket"},
    "date":                 {"en": "Date",                  "vi": "Ngày"},
    "time_col":             {"en": "Time",                  "vi": "Giờ"},
    "candles":              {"en": "Candles",               "vi": "Số nến"},
    "status":               {"en": "Status",                "vi": "Trạng thái"},
    "test_mode":            {"en": "Test Mode",             "vi": "Chế độ Test"},
    "live_mode":            {"en": "Live Mode",             "vi": "Chế độ Live"},
    "running":              {"en": "Running",               "vi": "Đang chạy"},
    "stopped":              {"en": "Stopped",               "vi": "Đã dừng"},
    "active":               {"en": "Active",                "vi": "Hoạt động"},

    # ── MT5 / Credentials ──
    "no_mt5":               {"en": "MT5 not available (Windows only).", "vi": "MT5 không khả dụng (chỉ Windows)."},
    "no_credentials":       {"en": "MT5 account not configured. Please go to Settings to add your MT5 credentials.", "vi": "Chưa cấu hình tài khoản MT5. Vui lòng vào Cài đặt để thêm thông tin đăng nhập."},

    # ── Trade setup (shared Bots + Backtest) ──
    "section_market":       {"en": "Market",                "vi": "Thị trường"},
    "section_trade_setup":  {"en": "Trade Setup",           "vi": "Thiết lập lệnh"},
    "section_exit_rules":   {"en": "Exit Rules",            "vi": "Quy tắc thoát"},
    "section_position":     {"en": "Position Sizing",       "vi": "Quản lý vốn"},
    "entry_mode":           {"en": "Entry Mode",            "vi": "Kiểu vào lệnh"},
    "entry_mode_close":     {"en": "Close Price",           "vi": "Giá đóng cửa"},
    "entry_mode_range":     {"en": "Range Percent",         "vi": "% Biên độ"},
    "rr_ratio":             {"en": "RR Ratio",              "vi": "Tỷ lệ R:R"},
    "buffer_k":             {"en": "Buffer K (points)",     "vi": "Buffer K (điểm)"},
    "entry_percent":        {"en": "Entry Percent (%)",     "vi": "% Vào lệnh"},
    "retry_candles":        {"en": "Retry Candles",         "vi": "Số nến thử lại"},
    "expire_candles":       {"en": "Expire Candles",        "vi": "Số nến hết hạn"},
    "tp_type":              {"en": "TP Type",               "vi": "Kiểu chốt lời"},
    "tp_price":             {"en": "Price (wick)",          "vi": "Giá (bóng nến)"},
    "tp_close":             {"en": "Close (candle)",        "vi": "Đóng cửa (nến)"},
    "sl_type":              {"en": "SL Type",               "vi": "Kiểu cắt lỗ"},
    "sl_close":             {"en": "Close (candle)",        "vi": "Đóng cửa (nến)"},
    "sl_price":             {"en": "Price (wick)",          "vi": "Giá (bóng nến)"},
    "max_candles":          {"en": "Max Candles",           "vi": "Số nến tối đa"},
    "max_candles_limit":    {"en": "Limit",                 "vi": "Giới hạn"},
    "breakeven":            {"en": "Breakeven",             "vi": "Hòa vốn"},
    "breakeven_trigger":    {"en": "Trigger (%)",           "vi": "Kích hoạt (%)"},
    "breakeven_sl_target":  {"en": "SL Target",             "vi": "Đích SL"},
    "breakeven_entry":      {"en": "Entry Price",           "vi": "Giá vào lệnh"},
    "breakeven_close":      {"en": "Candle Close",          "vi": "Đóng cửa nến"},
    "lot_mode":             {"en": "Mode",                  "vi": "Chế độ"},
    "lot_fixed":            {"en": "Fixed Lot",             "vi": "Lot cố định"},
    "lot_flex":             {"en": "Flex (Risk-based)",     "vi": "Linh hoạt (theo rủi ro)"},
    "lot_size":             {"en": "Lot Size",              "vi": "Khối lượng"},
    "starting_equity":      {"en": "Starting Equity ($)",   "vi": "Vốn ban đầu ($)"},
    "risk_mode":            {"en": "Risk Mode",             "vi": "Kiểu rủi ro"},
    "risk_pct_label":       {"en": "%",                     "vi": "%"},
    "risk_fixed_label":     {"en": "Fixed $",               "vi": "Cố định $"},
    "risk_per_trade_pct":   {"en": "Risk/Trade (%)",        "vi": "Rủi ro/Lệnh (%)"},
    "risk_per_trade_usd":   {"en": "Risk/Trade ($)",        "vi": "Rủi ro/Lệnh ($)"},
    "compounding":          {"en": "Compounding",           "vi": "Lãi kép"},
    "validate_config":      {"en": "Validate Config",       "vi": "Kiểm tra cấu hình"},

    # ── Batch entry times ──
    "batch_entry_times":    {"en": "Batch Entry Times",     "vi": "Nhiều giờ vào lệnh"},
    "batch_comma_times":    {"en": "Comma-separated times", "vi": "Các giờ cách nhau bởi dấu phẩy"},
    "batch_enable":         {"en": "Enable batch mode",     "vi": "Bật chế độ nhiều giờ"},

    # ── Bots page ──
    "page_bots":            {"en": "Bot Management",        "vi": "Quản lý Bot"},
    "running_bots":         {"en": "Running Bots",          "vi": "Bot đang chạy"},
    "create_bot":           {"en": "Create New Bot",        "vi": "Tạo Bot mới"},
    "bot_history":          {"en": "Bot History & Analysis","vi": "Lịch sử & Phân tích Bot"},
    "strategies_count":     {"en": "Strategies",            "vi": "Chiến lược"},
    "stop_all":             {"en": "Stop All My Bots",      "vi": "Dừng tất cả Bot"},
    "only_my_bots":         {"en": "Only my bots",          "vi": "Chỉ bot của tôi"},
    "test_only":            {"en": "Test Only",             "vi": "Chỉ Test"},
    "live_only":            {"en": "Live Only",             "vi": "Chỉ Live"},
    "stop_bot":             {"en": "Stop",                  "vi": "Dừng"},
    "restart_bot":          {"en": "Restart",               "vi": "Khởi động lại"},
    "config_details":       {"en": "Config Details",        "vi": "Chi tiết cấu hình"},
    "load_config":          {"en": "Load this config",      "vi": "Tải cấu hình này"},
    "load_from_past":       {"en": "Load from past config", "vi": "Tải từ cấu hình cũ"},
    "select_config":        {"en": "Select config",         "vi": "Chọn cấu hình"},
    "load_selected":        {"en": "Load selected config",  "vi": "Tải cấu hình đã chọn"},
    "start_bot":            {"en": "Start Bot",             "vi": "Khởi động Bot"},
    "start_n_bots":         {"en": "Start {n} Bots",        "vi": "Khởi động {n} Bot"},
    "preset_name":          {"en": "Preset name",           "vi": "Tên preset"},
    "save_preset":          {"en": "Save Preset",           "vi": "Lưu Preset"},
    "select_record":        {"en": "Select record",         "vi": "Chọn bản ghi"},
    "load_into_create":     {"en": "Load into Create Bot",  "vi": "Tải vào Tạo Bot"},
    "delete_record":        {"en": "Delete record",         "vi": "Xóa bản ghi"},
    "perf_analysis":        {"en": "Performance Analysis",  "vi": "Phân tích hiệu suất"},
    "perf_by_config":       {"en": "Performance by Configuration", "vi": "Hiệu suất theo cấu hình"},
    "config_history":       {"en": "Config History",        "vi": "Lịch sử cấu hình"},
    "no_bots_running":      {"en": "No bots running. Create one in the 'Create Bot' tab.", "vi": "Không có bot nào đang chạy. Tạo mới ở tab 'Tạo Bot'."},
    "no_bots_match":        {"en": "No bots match the filters", "vi": "Không có bot nào khớp bộ lọc"},
    "found_bots":           {"en": "Found {n} bot(s)",      "vi": "Tìm thấy {n} bot"},
    "config_loaded":        {"en": "Config loaded! Switch to Create Bot tab.", "vi": "Đã tải cấu hình! Chuyển sang tab Tạo Bot."},
    "no_saved_configs":     {"en": "No saved configs yet.", "vi": "Chưa có cấu hình nào được lưu."},
    "no_strategies":        {"en": "No strategies available.", "vi": "Chưa có chiến lược nào."},
    "config_valid":         {"en": "Configuration is valid!", "vi": "Cấu hình hợp lệ!"},
    "fix_errors":           {"en": "Fix errors above before starting.", "vi": "Hãy sửa lỗi ở trên trước khi bắt đầu."},
    "starting_bots":        {"en": "Starting bots...",      "vi": "Đang khởi động bot..."},
    "bots_started":         {"en": "{n} bot(s) started!",   "vi": "{n} bot đã được khởi động!"},
    "bots_failed":          {"en": "{n} bot(s) failed.",    "vi": "{n} bot khởi động thất bại."},
    "no_config_history":    {"en": "No config history yet. Start a bot or save a preset to begin.", "vi": "Chưa có lịch sử cấu hình. Hãy khởi động bot hoặc lưu preset."},
    "no_trade_history":     {"en": "No trade history found. Run some bots first!", "vi": "Chưa có lịch sử giao dịch. Hãy chạy bot trước!"},
    "no_trades_recorded":   {"en": "No trades recorded yet.", "vi": "Chưa có giao dịch nào được ghi lại."},
    "no_trades_found":      {"en": "No trades found.",      "vi": "Không tìm thấy giao dịch."},
    "found_trades":         {"en": "Found {n} trades",      "vi": "Tìm thấy {n} giao dịch"},

    # ── Orders page ──
    "page_orders":          {"en": "Orders Management",     "vi": "Quản lý Lệnh"},
    "account_info":         {"en": "Account Info",          "vi": "Thông tin tài khoản"},
    "all_positions":        {"en": "All Positions",         "vi": "Tất cả vị thế"},
    "bot_orders":           {"en": "Bot Orders",            "vi": "Lệnh Bot"},
    "bot_orders_only":      {"en": "Bot Orders Only",       "vi": "Chỉ lệnh Bot"},
    "place_manual":         {"en": "Place Manual Order",    "vi": "Đặt lệnh thủ công"},
    "manual_close_history": {"en": "Manual Close History",  "vi": "Lịch sử đóng lệnh thủ công"},
    "refresh_positions":    {"en": "Refresh Positions",     "vi": "Làm mới vị thế"},
    "auto_refresh":         {"en": "Auto-refresh",          "vi": "Tự động làm mới"},
    "interval":             {"en": "Interval",              "vi": "Chu kỳ"},
    "close_pos":            {"en": "Close",                 "vi": "Đóng"},
    "close_all":            {"en": "Close All Positions",   "vi": "Đóng tất cả vị thế"},
    "refresh_bot_orders":   {"en": "Refresh Bot Orders",    "vi": "Làm mới lệnh Bot"},
    "close_position":       {"en": "Close Position",        "vi": "Đóng vị thế"},
    "custom_symbol":        {"en": "Custom symbol",         "vi": "Cặp tiền tùy chỉnh"},
    "set_sl_tp":            {"en": "Set SL/TP",             "vi": "Đặt SL/TP"},
    "sl_pips":              {"en": "SL (pips)",             "vi": "SL (pips)"},
    "tp_pips":              {"en": "TP (pips)",             "vi": "TP (pips)"},
    "place_order":          {"en": "Place {dir} Order",     "vi": "Đặt lệnh {dir}"},
    "floating_pnl":         {"en": "Floating P&L",         "vi": "P&L thả nổi"},
    "free_margin":          {"en": "Free Margin",           "vi": "Ký quỹ khả dụng"},
    "current_price":        {"en": "Current Price",         "vi": "Giá hiện tại"},
    "stop_loss":            {"en": "Stop Loss",             "vi": "Cắt lỗ"},
    "take_profit":          {"en": "Take Profit",           "vi": "Chốt lời"},
    "distance":             {"en": "Distance",              "vi": "Khoảng cách"},
    "no_bot_orders":        {"en": "No bot orders found. Bots will appear here when they place orders.", "vi": "Chưa có lệnh bot. Bot sẽ xuất hiện ở đây khi đặt lệnh."},
    "no_open_positions":    {"en": "No open positions",     "vi": "Không có vị thế đang mở"},
    "found_positions":      {"en": "Found {n} open position(s)", "vi": "Tìm thấy {n} vị thế đang mở"},
    "found_bot_orders":     {"en": "Found {n} bot order(s)","vi": "Tìm thấy {n} lệnh bot"},
    "placing_order":        {"en": "Placing order...",      "vi": "Đang đặt lệnh..."},
    "order_placed":         {"en": "Order placed! {msg}",   "vi": "Đã đặt lệnh! {msg}"},
    "order_failed":         {"en": "Order failed: {msg}",   "vi": "Đặt lệnh thất bại: {msg}"},
    "closed_positions":     {"en": "Closed {n} position(s)", "vi": "Đã đóng {n} vị thế"},
    "no_manual_closes":     {"en": "No manual closes recorded yet", "vi": "Chưa có lệnh đóng thủ công nào"},
    "bot_orders_caption":   {"en": "Orders placed by trading bots (identified by 'BotForex' comment)", "vi": "Lệnh được đặt bởi bot (nhận dạng qua comment 'BotForex')"},
    "connect_mt5":          {"en": "Connect to MT5 on Windows to manage real positions", "vi": "Kết nối MT5 trên Windows để quản lý vị thế thực"},

    # ── Signals page ──
    "page_signals":         {"en": "Signal History",        "vi": "Lịch sử tín hiệu"},
    "statistics":           {"en": "Statistics",            "vi": "Thống kê"},
    "filter_signals":       {"en": "Filter Signals",        "vi": "Lọc tín hiệu"},
    "signal_list":          {"en": "Signal List",           "vi": "Danh sách tín hiệu"},
    "add_manual_signal":    {"en": "Add Manual Signal (Testing)", "vi": "Thêm tín hiệu thủ công (Test)"},
    "result":               {"en": "Result",                "vi": "Kết quả"},
    "date_range":           {"en": "Date Range",            "vi": "Khoảng thời gian"},
    "add_signal":           {"en": "Add Signal",            "vi": "Thêm tín hiệu"},
    "clear_all_signals":    {"en": "Clear All Signals",     "vi": "Xóa tất cả tín hiệu"},
    "total_trades":         {"en": "Total Trades",          "vi": "Tổng giao dịch"},
    "wins":                 {"en": "Wins",                  "vi": "Thắng"},
    "win_rate":             {"en": "Win Rate",              "vi": "Tỷ lệ thắng"},
    "losses":               {"en": "Losses",                "vi": "Thua"},
    "total_pnl":            {"en": "Total P&L",             "vi": "Tổng P&L"},
    "avg_pnl":              {"en": "Avg P&L",               "vi": "P&L trung bình"},
    "best_trade":           {"en": "Best Trade",            "vi": "Lệnh tốt nhất"},
    "worst_trade":          {"en": "Worst Trade",           "vi": "Lệnh tệ nhất"},
    "no_signals":           {"en": "No signals recorded yet. Run the bot to generate signals.", "vi": "Chưa có tín hiệu. Hãy chạy bot để tạo tín hiệu."},
    "signal_added":         {"en": "Signal added!",         "vi": "Đã thêm tín hiệu!"},
    "signals_cleared":      {"en": "All signals cleared!",  "vi": "Đã xóa tất cả tín hiệu!"},
    "manual_signal_caption":{"en": "Use this to manually add signals for testing purposes", "vi": "Dùng để thêm tín hiệu thủ công cho mục đích kiểm tra"},
    "exit_type":            {"en": "Exit Type",             "vi": "Kiểu thoát"},
    "exit_price":           {"en": "Exit Price",            "vi": "Giá thoát"},

    # ── Strategies page ──
    "page_strategies":      {"en": "Strategy Management",   "vi": "Quản lý chiến lược"},
    "all_strategies":       {"en": "All Strategies",        "vi": "Tất cả chiến lược"},
    "create_strategy":      {"en": "Create New Strategy",   "vi": "Tạo chiến lược mới"},
    "view_edit_strategy":   {"en": "View / Edit Strategy",  "vi": "Xem / Sửa chiến lược"},
    "strategy_id":          {"en": "Strategy ID*",          "vi": "ID chiến lược*"},
    "strategy_name":        {"en": "Strategy Name*",        "vi": "Tên chiến lược*"},
    "entry_rules":          {"en": "Entry Rules:",          "vi": "Quy tắc vào lệnh:"},
    "exit_config":          {"en": "Exit Configuration:",   "vi": "Cấu hình thoát lệnh:"},
    "parameters":           {"en": "Parameters:",           "vi": "Tham số:"},
    "symbols_label":        {"en": "Symbols:",              "vi": "Cặp tiền:"},
    "symbols_input":        {"en": "Symbols (comma-separated)", "vi": "Cặp tiền (cách nhau bởi dấu phẩy)"},
    "exit_types":           {"en": "Exit Types",            "vi": "Kiểu thoát lệnh"},
    "create_strategy_btn":  {"en": "Create Strategy",       "vi": "Tạo chiến lược"},
    "select_strategy":      {"en": "Select Strategy",       "vi": "Chọn chiến lược"},
    "save_changes":         {"en": "Save Changes",          "vi": "Lưu thay đổi"},
    "disable_btn":          {"en": "Disable",               "vi": "Tắt"},
    "enable_btn":           {"en": "Enable",                "vi": "Bật"},
    "no_strategies_info":   {"en": "No strategies found. Create one in the 'Create Strategy' tab.", "vi": "Chưa có chiến lược. Tạo mới ở tab 'Tạo chiến lược'."},
    "strategy_created":     {"en": "Strategy '{name}' created!", "vi": "Đã tạo chiến lược '{name}'!"},
    "strategy_updated":     {"en": "Strategy updated!",     "vi": "Đã cập nhật chiến lược!"},
    "strategy_id_required": {"en": "Strategy ID and Name are required", "vi": "ID và Tên chiến lược là bắt buộc"},
    "no_strategies_avail":  {"en": "No strategies available", "vi": "Không có chiến lược nào"},
    "failed_load_strategy": {"en": "Failed to load strategy", "vi": "Không thể tải chiến lược"},
    "edit_strategy_warn":   {"en": "Edit strategy by modifying values below", "vi": "Chỉnh sửa chiến lược bằng cách thay đổi giá trị bên dưới"},

    # ── Simulation page ──
    "page_simulation":      {"en": "Strategy Simulation",   "vi": "Mô phỏng chiến lược"},
    "simulation_caption":   {"en": "Run single simulation on live MT5 data", "vi": "Chạy mô phỏng đơn trên dữ liệu MT5 trực tiếp"},
    "sim_params":           {"en": "Simulation Parameters", "vi": "Tham số mô phỏng"},
    "run_simulation":       {"en": "Run Simulation",        "vi": "Chạy mô phỏng"},
    "connecting_sim":       {"en": "Connecting to MT5 and running simulation...", "vi": "Đang kết nối MT5 và chạy mô phỏng..."},
    "sim_completed":        {"en": "Simulation completed!", "vi": "Mô phỏng hoàn tất!"},
    "master_candle":        {"en": "Master Candle: {time}", "vi": "Nến chủ: {time}"},
    "candle_tracking":      {"en": "Candle Tracking",       "vi": "Theo dõi nến"},
    "exit_rules_explained": {"en": "Exit Rules Explained",  "vi": "Giải thích quy tắc thoát"},
    "mt5_live_enabled":     {"en": "MT5 available - Live simulation enabled", "vi": "MT5 khả dụng - Mô phỏng trực tiếp được bật"},
    "mt5_demo_mode":        {"en": "MT5 not available (Windows only) - Demo mode", "vi": "MT5 không khả dụng (chỉ Windows) - Chế độ demo"},
    "no_strategies_default":{"en": "No strategies defined. Using default parameters.", "vi": "Chưa có chiến lược. Đang dùng tham số mặc định."},
    "doji_detected":        {"en": "Doji candle detected - no trade signal", "vi": "Phát hiện nến Doji - không có tín hiệu giao dịch"},
    "no_data_symbol":       {"en": "No data for {symbol}",  "vi": "Không có dữ liệu cho {symbol}"},

    # ── Users page ──
    "page_users":           {"en": "User Management",       "vi": "Quản lý người dùng"},
    "current_users":        {"en": "Current Users",         "vi": "Người dùng hiện tại"},
    "register_user":        {"en": "Register New User",     "vi": "Đăng ký người dùng mới"},
    "delete_user":          {"en": "Delete User",           "vi": "Xóa người dùng"},
    "change_password":      {"en": "Change User Password",  "vi": "Đổi mật khẩu"},
    "full_name":            {"en": "Full Name*",            "vi": "Họ và tên*"},
    "confirm_password":     {"en": "Confirm Password*",     "vi": "Xác nhận mật khẩu*"},
    "new_password":         {"en": "New Password",          "vi": "Mật khẩu mới"},
    "confirm_new_password": {"en": "Confirm New Password",  "vi": "Xác nhận mật khẩu mới"},
    "user_role":            {"en": "user",                  "vi": "người dùng"},
    "admin_role":           {"en": "admin",                 "vi": "quản trị viên"},
    "register_btn":         {"en": "Register User",         "vi": "Đăng ký người dùng"},
    "select_user_delete":   {"en": "Select user to delete", "vi": "Chọn người dùng để xóa"},
    "delete_user_btn":      {"en": "Delete User",           "vi": "Xóa người dùng"},
    "select_user":          {"en": "Select user",           "vi": "Chọn người dùng"},
    "change_password_btn":  {"en": "Change Password",       "vi": "Đổi mật khẩu"},
    "access_denied":        {"en": "Access denied. Admin only.", "vi": "Truy cập bị từ chối. Chỉ dành cho Admin."},
    "admin_logged":         {"en": "Admin: {name}",         "vi": "Admin: {name}"},
    "no_users":             {"en": "No users found",        "vi": "Không tìm thấy người dùng"},
    "fill_required":        {"en": "Please fill in all required fields (*)", "vi": "Vui lòng điền đầy đủ các trường bắt buộc (*)"},
    "password_min":         {"en": "Password must be at least 6 characters", "vi": "Mật khẩu phải có ít nhất 6 ký tự"},
    "password_mismatch":    {"en": "Passwords do not match", "vi": "Mật khẩu không khớp"},
    "username_exists":      {"en": "Username '{u}' already exists", "vi": "Tên đăng nhập '{u}' đã tồn tại"},
    "user_registered":      {"en": "User '{u}' registered successfully!", "vi": "Đã đăng ký người dùng '{u}' thành công!"},
    "failed_register":      {"en": "Failed to register user", "vi": "Đăng ký người dùng thất bại"},
    "cant_delete_self":     {"en": "Cannot delete yourself", "vi": "Không thể xóa chính bạn"},
    "user_deleted":         {"en": "User '{u}' deleted",    "vi": "Đã xóa người dùng '{u}'"},
    "no_users_to_delete":   {"en": "No users to delete (only you exist)", "vi": "Không có người dùng để xóa (chỉ còn bạn)"},
    "password_changed":     {"en": "Password changed for '{u}'", "vi": "Đã đổi mật khẩu cho '{u}'"},

    # ── Settings page ──
    "page_settings":        {"en": "Settings",              "vi": "Cài đặt"},
    "mt5_account":          {"en": "Your MT5 Account",      "vi": "Tài khoản MT5 của bạn"},
    "test_connection":      {"en": "Test Connection",       "vi": "Kiểm tra kết nối"},
    "telegram_config":      {"en": "Telegram Configuration (Admin)", "vi": "Cấu hình Telegram (Admin)"},
    "system_config":        {"en": "System Configuration",  "vi": "Cấu hình hệ thống"},
    "information":          {"en": "Information",           "vi": "Thông tin"},
    "view_env":             {"en": "View .env (masked)",    "vi": "Xem .env (ẩn)"},
    "mt5_login":            {"en": "MT5 Login",             "vi": "Đăng nhập MT5"},
    "mt5_server":           {"en": "MT5 Server",            "vi": "Server MT5"},
    "mt5_password":         {"en": "MT5 Password",          "vi": "Mật khẩu MT5"},
    "trading_symbol":       {"en": "Trading Symbol",        "vi": "Cặp tiền giao dịch"},
    "save_mt5_creds":       {"en": "Save MT5 Credentials",  "vi": "Lưu thông tin MT5"},
    "test_mt5_conn":        {"en": "Test MT5 Connection",   "vi": "Kiểm tra kết nối MT5"},
    "bot_token":            {"en": "Bot Token",             "vi": "Token Bot"},
    "main_chat_id":         {"en": "Main Chat ID",          "vi": "ID Chat chính"},
    "error_chat_id":        {"en": "Error Chat ID",         "vi": "ID Chat lỗi"},
    "test_chat_id":         {"en": "Test Chat ID",          "vi": "ID Chat test"},
    "test_telegram":        {"en": "Test Telegram",         "vi": "Kiểm tra Telegram"},
    "mt5_configured":       {"en": "MT5 account configured", "vi": "Đã cấu hình tài khoản MT5"},
    "mt5_not_configured":   {"en": "MT5 account not configured. Please enter your credentials below.", "vi": "Chưa cấu hình MT5. Vui lòng nhập thông tin đăng nhập bên dưới."},
    "save_mt5_success":     {"en": "MT5 credentials saved!", "vi": "Đã lưu thông tin MT5!"},
    "fill_mt5_fields":      {"en": "Please fill in all MT5 fields", "vi": "Vui lòng điền đầy đủ thông tin MT5"},
    "connected_balance":    {"en": "Connected! Balance: ${bal:,.2f}", "vi": "Đã kết nối! Số dư: ${bal:,.2f}"},
    "msg_sent":             {"en": "Message sent!",         "vi": "Đã gửi tin nhắn!"},
    "logged_as_admin":      {"en": "Logged in as Admin: {name}", "vi": "Đăng nhập với tư cách Admin: {name}"},
    "logged_as_user":       {"en": "Logged in as: {name}", "vi": "Đăng nhập với tư cách: {name}"},

    # ── UI Mode (Simple / Advanced) ──
    "ui_mode_label":        {"en": "Interface Mode",        "vi": "Giao diện"},
    "ui_mode_simple":       {"en": "🟢 Simple",             "vi": "🟢 Đơn giản"},
    "ui_mode_advanced":     {"en": "⚙️ Advanced",           "vi": "⚙️ Nâng cao"},
    "simple_mode_hint":     {"en": "Advanced settings hidden. Switch to ⚙️ Advanced to see all options.", "vi": "Đang ẩn cài đặt nâng cao. Chuyển sang ⚙️ Nâng cao để xem tất cả."},

    # ── Config Summary Card ──
    "config_preview":       {"en": "📋 Configuration Preview",  "vi": "📋 Xem lại cấu hình"},
    "confirm_start":        {"en": "Review before starting:",    "vi": "Kiểm tra trước khi khởi động:"},
    "preview_symbol":       {"en": "Symbol",                     "vi": "Cặp tiền"},
    "preview_strategy":     {"en": "Strategy",                   "vi": "Chiến lược"},
    "preview_entry":        {"en": "Entry",                      "vi": "Vào lệnh"},
    "preview_exit":         {"en": "Exit",                       "vi": "Thoát lệnh"},
    "preview_sizing":       {"en": "Position",                   "vi": "Khối lượng"},

    # ── Tooltips: Trade Setup ──
    "tip_rr_ratio":         {
        "en": "Risk:Reward ratio.\nRR=2 → TP is 2× the SL distance.\nHigher = bigger profit target, harder to reach.\nRecommended: 1.5–3.0",
        "vi": "Tỷ lệ rủi ro:lợi nhuận.\nRR=2 → TP gấp 2 lần khoảng cách SL.\nCao hơn = lợi nhuận lớn hơn nhưng khó đạt.\nKhuyến nghị: 1.5–3.0"
    },
    "tip_buffer_k":         {
        "en": "Extra points beyond candle wick added to SL (protection buffer).\nXAUUSD: 1pt = $0.01 → 5pts = $0.05 buffer\nForex: 1pt = 0.00001\nBTCUSD: 1pt = $1",
        "vi": "Điểm thêm vào ngoài đuôi nến cho SL (vùng đệm bảo vệ).\nXAUUSD: 1pt = $0.01 → 5pts = $0.05 buffer\nForex: 1pt = 0.00001"
    },
    "tip_entry_mode":       {
        "en": "Close: enter at candle close price (instant, no waiting).\nRange %: place LIMIT order at X% retracement into candle body (waits for pullback).",
        "vi": "Đóng cửa: vào lệnh tại giá đóng cửa (ngay lập tức, không chờ).\n% Biên độ: đặt lệnh LIMIT tại X% vào thân nến (chờ pullback)."
    },
    "tip_entry_percent":    {
        "en": "How deep into the candle body to place the LIMIT entry.\n0% = at close price (no pullback)\n50% = halfway into body\n100% = at open price\nRecommended: 20%–50%",
        "vi": "Độ sâu vào thân nến để đặt lệnh LIMIT.\n0% = tại giá đóng (không pullback)\n50% = giữa thân nến\n100% = tại giá mở\nKhuyến nghị: 20%–50%"
    },
    "tip_expire_candles":   {
        "en": "Cancel LIMIT order if not filled after this many candles.\n0 = wait forever until filled or SL hit.\nM5: 5 candles = 25 minutes",
        "vi": "Hủy lệnh LIMIT nếu chưa khớp sau số nến này.\n0 = chờ mãi đến khi khớp hoặc chạm SL.\nM5: 5 nến = 25 phút"
    },
    "tip_retry_candles":    {
        "en": "If broker rejects LIMIT placement, retry on next candle. Stop after N attempts.\nUseful when broker has strict stop-level restrictions.",
        "vi": "Nếu broker từ chối đặt lệnh LIMIT, thử lại lần sau. Dừng sau N lần.\nHữu ích khi broker có giới hạn stop-level nghiêm ngặt."
    },

    # ── Tooltips: Exit Rules ──
    "tip_tp_price":         {
        "en": "TP triggers when price WICK touches TP level (even for 1 tick).\nMore aggressive — exits faster but may miss continuation.",
        "vi": "TP kích hoạt khi bóng nến chạm mức TP (dù chỉ 1 tick).\nTích cực hơn — thoát nhanh hơn."
    },
    "tip_tp_close":         {
        "en": "TP triggers only when candle CLOSES beyond TP.\nMore conservative — avoids false breakouts, but gives up some profit.",
        "vi": "TP kích hoạt khi nến đóng cửa vượt qua TP.\nBảo thủ hơn — tránh breakout giả, nhưng có thể mất một phần lợi nhuận."
    },
    "tip_sl_price":         {
        "en": "SL triggers when price WICK touches SL level.\nStrict — protects capital but can be stopped by short spikes.",
        "vi": "SL kích hoạt khi bóng nến chạm mức SL.\nNghiêm ngặt — bảo vệ vốn nhưng có thể bị dừng bởi spike ngắn."
    },
    "tip_sl_close":         {
        "en": "SL triggers only when candle CLOSES beyond SL.\nMore forgiving — survives temporary spikes, but larger drawdown if trend reverses.",
        "vi": "SL kích hoạt khi nến đóng cửa vượt SL.\nKhoan dung hơn — sống sót qua spike tạm thời, nhưng drawdown lớn hơn nếu đảo chiều."
    },
    "tip_max_candles":      {
        "en": "Force-close trade after N candles if neither TP nor SL is hit.\nPrevents trades from holding too long.\nM5 timeframe: 7 candles = 35 minutes",
        "vi": "Đóng lệnh bắt buộc sau N nến nếu chưa đạt TP/SL.\nTránh giữ lệnh quá lâu.\nKhung M5: 7 nến = 35 phút"
    },
    "tip_breakeven":        {
        "en": "Move SL to entry price when trade reaches X% towards TP.\nExample: 50% trigger → SL moves to entry when halfway to TP.\nEliminates risk of a loss after a winning trade.",
        "vi": "Dời SL về giá vào lệnh khi lệnh đạt X% đường đến TP.\nVí dụ: kích hoạt 50% → SL về entry khi đi được nửa đường đến TP.\nLoại bỏ rủi ro thua lỗ sau một lệnh đang thắng."
    },

    # ── Tooltips: Position Sizing ──
    "tip_lot_fixed":        {
        "en": "Trade the same lot size for every trade, regardless of account balance.\nSimple but doesn't scale with account growth.",
        "vi": "Giao dịch cùng khối lượng lot cho mọi lệnh, bất kể số dư.\nĐơn giản nhưng không tự động tăng theo tài khoản."
    },
    "tip_lot_flex":         {
        "en": "Automatically calculate lot size to risk a % of your equity per trade.\nSmarter risk management — lot grows/shrinks with your account.",
        "vi": "Tự động tính khối lượng để rủi ro một % vốn mỗi lệnh.\nQuản lý rủi ro thông minh hơn — lot tự tăng/giảm theo tài khoản."
    },
    "tip_starting_equity":  {
        "en": "Account balance used to calculate lot size.\nCompounding OFF: always uses this fixed value.\nCompounding ON: uses real-time account equity.",
        "vi": "Số dư tài khoản dùng để tính khối lượng.\nTắt lãi kép: luôn dùng giá trị này.\nBật lãi kép: dùng vốn thực tế hiện tại."
    },
    "tip_compounding":      {
        "en": "ON: Risk % of current equity (lot grows as account grows — compounding effect).\nOFF: Risk % of starting equity (fixed dollar risk per trade).\nExample with 1%, $1000: ON→lot varies | OFF→always risk $10",
        "vi": "BẬT: Rủi ro % vốn hiện tại (lot tăng khi tài khoản tăng — hiệu ứng lãi kép).\nTẮT: Rủi ro % vốn ban đầu (số tiền rủi ro cố định mỗi lệnh).\nVí dụ 1%, $1000: BẬT→lot thay đổi | TẮT→luôn rủi ro $10"
    },
    "tip_risk_percent":     {
        "en": "% of equity risked per trade (used to calculate lot size).\n1% on $1000 = risk $10/trade\n0.5% = conservative | 1% = standard | 2%+ = aggressive\nRecommended for beginners: 0.5%–1%",
        "vi": "% vốn rủi ro mỗi lệnh (dùng để tính khối lượng).\n1% trên $1000 = rủi ro $10/lệnh\n0.5% = thận trọng | 1% = tiêu chuẩn | 2%+ = mạo hiểm\nKhuyến nghị cho người mới: 0.5%–1%"
    },
    "tip_risk_amount":      {
        "en": "Fixed dollar amount risked per trade regardless of account size.\nExample: $10 risk → always risk $10, lot size calculated automatically.",
        "vi": "Số tiền rủi ro cố định mỗi lệnh, bất kể kích cỡ tài khoản.\nVí dụ: rủi ro $10 → luôn rủi ro $10, khối lượng được tính tự động."
    },

    # ── Backtest page ──
    "page_backtest":        {"en": "Backtest Strategy",     "vi": "Kiểm thử chiến lược"},
    "fetching_data":        {"en": "Fetching historical data...", "vi": "Đang tải dữ liệu lịch sử..."},
    "fetched_candles":      {"en": "Fetched {n} candles",   "vi": "Đã tải {n} nến"},
    "starting_backtest":    {"en": "Starting backtest...",  "vi": "Đang bắt đầu kiểm thử..."},
    "running_time":         {"en": "Running {t}... ({i}/{n})", "vi": "Đang chạy {t}... ({i}/{n})"},
    "complete":             {"en": "Complete!",             "vi": "Hoàn tất!"},
    "run_backtest":         {"en": "Run Backtest",          "vi": "Chạy kiểm thử"},
    "run_batch":            {"en": "Run Batch Backtest ({n} entry times)", "vi": "Chạy hàng loạt ({n} giờ vào lệnh)"},
    "batch_done":           {"en": "Completed {n} backtests. Results saved to history.", "vi": "Hoàn tất {n} kiểm thử. Kết quả đã lưu."},
    "failed_fetch":         {"en": "Failed to fetch data: {err}", "vi": "Không thể tải dữ liệu: {err}"},
    "no_data_period":       {"en": "No data found for the selected period", "vi": "Không có dữ liệu cho khoảng thời gian đã chọn"},
    "batch_results":        {"en": "Batch Results: {name}", "vi": "Kết quả hàng loạt: {name}"},
    "comparing":            {"en": "Comparing {n} entry times for {sym}", "vi": "So sánh {n} giờ vào lệnh cho {sym}"},

    # ── Log management ──
    "view_log":             {"en": "View Log",                "vi": "Xem Log"},
    "download_log":         {"en": "Download Log",            "vi": "Tải Log"},
    "recent_logs":          {"en": "Recent Logs",             "vi": "Log gần đây"},
    "filter_level":         {"en": "Filter Level",            "vi": "Lọc mức độ"},
    "lines_to_show":        {"en": "Lines to show",           "vi": "Số dòng hiển thị"},
    "select_log_file":      {"en": "Select log file",         "vi": "Chọn file log"},
    "no_recent_logs":       {"en": "No recent logs found.",   "vi": "Không tìm thấy log gần đây."},
    "no_matching_lines":    {"en": "No matching lines.",      "vi": "Không có dòng nào khớp."},
    "log_management":       {"en": "Log Management",          "vi": "Quản lý Log"},
    "total_log_files":      {"en": "Total Log Files",         "vi": "Tổng file log"},
    "empty_log_files":      {"en": "Empty Files",             "vi": "File trống"},
    "log_size_mb":          {"en": "Log Size (MB)",           "vi": "Dung lượng (MB)"},
    "newest_log":           {"en": "Newest Log",              "vi": "Log mới nhất"},
    "clean_empty_logs":     {"en": "Clean Empty Logs",        "vi": "Xóa log trống"},
    "clean_old_logs":       {"en": "Clean Old Logs",          "vi": "Xóa log cũ"},
    "max_age_days":         {"en": "Max age (days)",          "vi": "Tuổi tối đa (ngày)"},
    "cleaned_empty":        {"en": "Deleted {n} empty log files.", "vi": "Đã xóa {n} file log trống."},
    "cleaned_old":          {"en": "Deleted {n} old log files.",   "vi": "Đã xóa {n} file log cũ."},

    # ── Dashboard (app.py) ──
    "page_dashboard":           {"en": "BotForex Dashboard",             "vi": "Bảng điều khiển BotForex"},
    "login_title":              {"en": "BotForex",                        "vi": "BotForex"},
    "login_subtitle":           {"en": "Login to Dashboard",             "vi": "Đăng nhập vào Bảng điều khiển"},
    "welcome_user":             {"en": "Welcome, {name}!",               "vi": "Xin chào, {name}!"},
    "bot_status_label":         {"en": "Bot Status",                     "vi": "Trạng thái Bot"},
    "todays_signals":           {"en": "Today's Signals",                "vi": "Tín hiệu hôm nay"},
    "total_pnl_label":          {"en": "Total P&L",                      "vi": "Tổng lãi/lỗ"},
    "strategy_rules":           {"en": "Strategy Rules",                 "vi": "Quy tắc chiến lược"},
    "quick_actions":            {"en": "Quick Actions",                  "vi": "Thao tác nhanh"},
    "refresh_data":             {"en": "Refresh Data",                   "vi": "Làm mới dữ liệu"},
    "test_telegram_btn":        {"en": "Test Telegram",                  "vi": "Kiểm tra Telegram"},
    "run_simulation_btn":       {"en": "Run Simulation",                 "vi": "Chạy mô phỏng"},
    "demo_credentials":         {"en": "Demo Credentials",               "vi": "Thông tin đăng nhập demo"},
    "login_error":              {"en": "Username/password is incorrect", "vi": "Tên đăng nhập/mật khẩu không đúng"},
    "login_prompt":             {"en": "Please enter your username and password", "vi": "Vui lòng nhập tên đăng nhập và mật khẩu"},
    "no_signals_caption":       {"en": "No signals yet. Bot will trigger at scheduled time.", "vi": "Chưa có tín hiệu. Bot sẽ kích hoạt vào giờ đã lên lịch."},
    "telegram_not_configured":  {"en": "Telegram not configured. Check Settings.", "vi": "Chưa cấu hình Telegram. Kiểm tra Cài đặt."},
    "telegram_send_failed":     {"en": "Failed to send message",         "vi": "Gửi tin nhắn thất bại"},
    "go_simulation":            {"en": "Go to Strategy page to run simulation", "vi": "Đến trang Chiến lược để chạy mô phỏng"},
    "recent_signals":           {"en": "Recent Signals",                 "vi": "Tín hiệu gần đây"},
    "entry_rules_desc":         {"en": "Entry Rules",                    "vi": "Quy tắc vào lệnh"},
    "risk_management_desc":     {"en": "Risk Management",                "vi": "Quản lý rủi ro"},
    "exit_rules_desc":          {"en": "Exit Rules",                     "vi": "Quy tắc thoát lệnh"},
    "master_candle_strategy":   {"en": "Master Candle Strategy",         "vi": "Chiến lược Nến chủ"},
    "logout":                   {"en": "Logout",                         "vi": "Đăng xuất"},
    "current_time_label":       {"en": "Current Time",                   "vi": "Thời gian hiện tại"},
    "risk_percent_label":       {"en": "Risk %",                         "vi": "Rủi ro %"},

    # ── Settings page extras ──
    "mt5_login_placeholder":    {"en": "Your MT5 account number",        "vi": "Số tài khoản MT5 của bạn"},
    "mt5_server_placeholder":   {"en": "e.g., Exness-MT5Trial8",         "vi": "VD: Exness-MT5Trial8"},
    "mt5_password_placeholder": {"en": "Your MT5 password",              "vi": "Mật khẩu MT5 của bạn"},
    "mt5_symbol_help":          {"en": "Standard: XAUUSDm | Pro/Raw: XAUUSD", "vi": "Tài khoản Standard: XAUUSDm | Pro/Raw: XAUUSD"},
    "save_failed":              {"en": "Failed to save credentials",     "vi": "Lưu thông tin đăng nhập thất bại"},
    "mt5_init_failed":          {"en": "MT5 initialization failed",      "vi": "Khởi tạo MT5 thất bại"},
    "mt5_creds_not_configured": {"en": "MT5 credentials not configured. Please save your credentials above.", "vi": "Chưa cấu hình thông tin MT5. Vui lòng lưu thông tin đăng nhập ở trên."},
    "login_failed":             {"en": "Login failed: {err}",            "vi": "Đăng nhập thất bại: {err}"},
    "telegram_signal_help":     {"en": "Main group for trade signals",   "vi": "Nhóm chính để nhận tín hiệu giao dịch"},
    "telegram_error_help":      {"en": "Group for error notifications",  "vi": "Nhóm nhận thông báo lỗi"},
    "telegram_test_help":       {"en": "Group for testing",              "vi": "Nhóm dành cho kiểm tra"},
    "mt5_account_info":         {"en": "MT5 Account: Each user has their own MT5 credentials.", "vi": "Tài khoản MT5: Mỗi người dùng có thông tin đăng nhập MT5 riêng."},
    "mt5_standard_info":        {"en": "Standard account: Use symbols with 'm' suffix (XAUUSDm)", "vi": "Tài khoản Standard: Dùng symbol có đuôi 'm' (XAUUSDm)"},
    "mt5_pro_info":             {"en": "Pro/Raw account: Use symbols without suffix (XAUUSD)", "vi": "Tài khoản Pro/Raw: Dùng symbol không có đuôi (XAUUSD)"},

    # ── Users page extras ──
    "placeholder_username":     {"en": "johndoe",                        "vi": "nguyenvana"},
    "placeholder_fullname":     {"en": "John Doe",                       "vi": "Nguyễn Văn A"},
    "placeholder_email":        {"en": "john@example.com",               "vi": "nguyenvana@email.com"},

    # ── UI status badges ──
    "status_running":           {"en": "Running",                        "vi": "Đang chạy"},
    "status_stopped":           {"en": "Stopped",                        "vi": "Đã dừng"},
    "status_waiting":           {"en": "Waiting",                        "vi": "Đang chờ"},
    "status_error":             {"en": "Error",                          "vi": "Lỗi"},
    "status_success":           {"en": "Success",                        "vi": "Thành công"},
}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def get_lang() -> str:
    """Return current language code: 'en' or 'vi'"""
    return st.session_state.get('app_lang', 'en')


def t(key: str, **kwargs) -> str:
    """Translate a key to the current language. Supports {placeholder} formatting."""
    lang = get_lang()
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang) or entry.get('en') or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def lang_toggle_button(container=None):
    """
    Render the language toggle button.
    Call once per page, passing st.sidebar or any st container.
    Defaults to st.sidebar.
    """
    current = get_lang()
    btn_label = "🇻🇳 Tiếng Việt" if current == "en" else "🇬🇧 English"
    c = container if container is not None else st.sidebar
    if c.button(btn_label, key="lang_toggle_btn"):
        st.session_state['app_lang'] = "vi" if current == "en" else "en"
        st.rerun()
