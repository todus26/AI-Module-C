from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Any

from flask import Flask, abort, g, jsonify, redirect, render_template_string, request, session, url_for

from inventory_agent import InventoryAgent


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "inventory.db"

ADMIN_PASSWORD = "admin1004"
DEFAULT_CATEGORIES = ("케이블", "공구", "소모품", "기타")
PER_PAGE = 10

app = Flask(__name__)
app.secret_key = "small-warehouse-secret-key"
inventory_agent = InventoryAgent(DB_PATH)


def today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error: Exception | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registered_date TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL UNIQUE,
            minimum_stock INTEGER NOT NULL DEFAULT 0 CHECK(minimum_stock >= 0),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_date TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL CHECK(movement_type IN ('입고', '출고')),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        """
    )
    for category in DEFAULT_CATEGORIES:
        db.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (category,))
    db.commit()


def paginate(total_count: int, page: int, per_page: int = PER_PAGE) -> dict[str, int]:
    total_pages = max(1, ceil(total_count / per_page)) if total_count else 1
    current_page = max(1, min(page, total_pages))
    offset = (current_page - 1) * per_page
    return {"page": current_page, "pages": total_pages, "offset": offset, "per_page": per_page}


def get_categories() -> list[sqlite3.Row]:
    return get_db().execute("SELECT id, name FROM categories ORDER BY name").fetchall()


def find_product(product_id: int) -> sqlite3.Row | None:
    return get_db().execute(
        """
        SELECT p.id, p.registered_date, p.name, p.minimum_stock, c.id AS category_id, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.id = ?
        """,
        (product_id,),
    ).fetchone()


def get_stock_map() -> dict[int, int]:
    rows = get_db().execute(
        """
        SELECT
            p.id AS product_id,
            COALESCE(SUM(CASE WHEN m.movement_type = '입고' THEN m.quantity ELSE -m.quantity END), 0) AS stock
        FROM products p
        LEFT JOIN movements m ON m.product_id = p.id
        GROUP BY p.id
        """
    ).fetchall()
    return {row["product_id"]: int(row["stock"]) for row in rows}


def require_admin() -> None:
    if not session.get("is_admin"):
        abort(403)


BASE_TEMPLATE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ title }} - 소형창고 재고관리</title>
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" />
  <style>
    :root {
      --action: #004dc1;
      --action-hover: #003fa3;
      --bright: #0069ed;
      --deep: #074499;
      --navy: #0a2864;
      --tint: #edf6fe;
      --wash: #dcedfd;

      --ink: #212529;
      --head: #1e1f21;
      --muted: #495057;
      --faint: #969faa;
      --line: #ced4da;
      --line-soft: #e8edf2;
      --bg: #f4f7fb;
      --surface: #ffffff;

      --low: #c0392b;
      --low-bg: #fdf2f0;
      --ok: #1f7a54;
      --ok-bg: #e8f6ef;

      --radius: 3px;
      --font: "Pretendard Variable", Pretendard, Inter, "Noto Sans KR", "Malgun Gothic", sans-serif;
    }
    * { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; }
    body {
      margin: 0;
      font-family: var(--font);
      font-size: 15px;
      font-weight: 400;
      line-height: 1.55;
      color: var(--ink);
      background: var(--bg);
    }
    a { color: var(--action); }
    :focus-visible { outline: 2px solid var(--bright); outline-offset: 2px; }

    .layout {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 232px minmax(0, 1fr);
      border-top: 4px solid var(--action);
    }

    .sidebar {
      position: sticky;
      top: 0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      padding: 28px 14px 18px;
      background: var(--surface);
      border-right: 1px solid var(--line-soft);
      color: var(--muted);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 11px;
      padding: 2px 10px 22px;
      color: var(--head);
      text-decoration: none;
    }
    .brand-mark {
      flex: none;
      width: 30px;
      height: 30px;
      border-radius: var(--radius);
      background:
        linear-gradient(#fff, #fff) 5px 5px / 8px 8px no-repeat,
        linear-gradient(#fff, #fff) 17px 5px / 8px 8px no-repeat,
        linear-gradient(#fff, #fff) 5px 17px / 8px 8px no-repeat,
        linear-gradient(#fff, #fff) 17px 17px / 8px 8px no-repeat,
        var(--action);
    }
    .brand-name {
      font-size: 17px;
      font-weight: 700;
      letter-spacing: -0.4px;
      line-height: 1.2;
      color: var(--action);
    }
    .brand-sub { font-size: 12.5px; color: var(--muted); font-weight: 500; }

    .group-title {
      margin: 16px 10px 5px;
      color: var(--muted);
      font-size: 12.5px;
      font-weight: 600;
    }
    .nav a {
      display: block;
      margin-bottom: 2px;
      padding: 8px 10px 8px 13px;
      border-left: 3px solid transparent;
      border-radius: 0 var(--radius) var(--radius) 0;
      color: var(--ink);
      font-weight: 500;
      text-decoration: none;
    }
    .nav a:hover { background: var(--tint); color: var(--action); }
    .nav a.active {
      background: var(--tint);
      border-left-color: var(--action);
      color: var(--action);
      font-weight: 600;
    }

    .admin {
      margin-top: auto;
      padding: 14px 10px 0;
      border-top: 1px solid var(--line-soft);
      font-size: 13.5px;
    }
    .admin a { color: var(--muted); text-decoration: none; }
    .admin a:hover { color: var(--action); text-decoration: underline; }
    .admin .who { display: block; margin-bottom: 6px; color: var(--head); font-weight: 600; }
    .admin .links { display: flex; gap: 14px; }

    .main {
      min-width: 0;
      padding: 28px 36px 48px;
      max-width: 1180px;
    }
    .head-row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 20px;
    }
    .head-row h1 {
      margin: 0;
      color: var(--head);
      font-size: 26px;
      font-weight: 700;
      letter-spacing: -0.4px;
      line-height: 1.25;
    }
    .date { color: var(--muted); font-size: 13.5px; font-variant-numeric: tabular-nums; }

    .flash {
      margin-bottom: 16px;
      padding: 10px 14px;
      border: 1px solid var(--wash);
      border-left: 3px solid var(--action);
      border-radius: var(--radius);
      background: var(--tint);
      font-size: 14.5px;
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      margin-bottom: 16px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 4px;
      background: var(--surface);
      box-shadow: inset 0 4px 0 var(--action);
    }
    .stat { padding: 18px 22px 16px; }
    .stat + .stat { border-left: 1px solid var(--line-soft); }
    .stat-label { color: var(--muted); font-size: 13.5px; font-weight: 500; }
    .stat-value {
      margin-top: 4px;
      color: var(--head);
      font-size: 28px;
      font-weight: 700;
      letter-spacing: -0.4px;
      line-height: 1.25;
      font-variant-numeric: tabular-nums;
    }
    .stat-value small { margin-left: 3px; color: var(--faint); font-size: 14px; font-weight: 500; letter-spacing: 0; }
    .stat.is-alert .stat-value { color: var(--low); }

    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
      gap: 16px;
      margin-bottom: 16px;
    }
    .card {
      min-width: 0;
      overflow-x: auto;
      padding: 18px 20px 20px;
      border: 1px solid var(--line);
      border-radius: 4px;
      background: var(--surface);
    }
    .card + .card { margin-top: 16px; }
    .cards .card + .card { margin-top: 0; }
    .card-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 10px;
      margin-bottom: 12px;
    }
    .card h3 { margin: 0 0 12px; color: var(--head); font-size: 16px; font-weight: 700; letter-spacing: -0.4px; }
    .card-head h3 { margin: 0; }
    .card-note { color: var(--faint); font-size: 13px; }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14.5px;
      font-variant-numeric: tabular-nums;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line-soft);
      text-align: left;
      white-space: nowrap;
    }
    th {
      padding-top: 8px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
      background: var(--bg);
    }
    td.num, th.num { text-align: right; }
    td.name { font-weight: 600; color: var(--head); }
    tbody tr:hover td { background: var(--tint); }
    tbody tr:last-child td { border-bottom: 0; }
    tr.is-low td { background: var(--low-bg); }
    tr.is-low td:first-child { box-shadow: inset 3px 0 0 var(--low); }
    tr.is-low:hover td { background: #fae6e2; }
    tr.is-selected td { background: var(--tint); }
    tr.is-selected td:first-child { box-shadow: inset 3px 0 0 var(--action); }
    .low-text { color: var(--low); font-weight: 700; }
    .empty { padding: 28px 12px; color: var(--muted); text-align: center; }

    .pill {
      display: inline-block;
      padding: 1px 8px;
      border-radius: var(--radius);
      background: var(--wash);
      color: var(--deep);
      font-size: 12.5px;
      font-weight: 600;
    }
    .pill.in { background: var(--wash); color: var(--action); }
    .pill.out { background: #eef1f4; color: var(--muted); }
    .pill.low { background: #f8d7d3; color: var(--low); }
    .pill.ok { background: var(--ok-bg); color: var(--ok); }

    .gauge {
      position: relative;
      width: 150px;
      height: 6px;
      border-radius: 1px;
      background: var(--line-soft);
    }
    .gauge i {
      position: absolute;
      inset: 0 auto 0 0;
      border-radius: 1px;
      background: var(--action);
    }
    .gauge.low i { background: var(--low); }
    .gauge::after {
      content: "";
      position: absolute;
      left: 50%;
      top: -3px;
      bottom: -3px;
      width: 1px;
      background: var(--ink);
      opacity: 0.35;
    }
    .gauge-legend { margin: 0 0 12px; color: var(--muted); font-size: 13.5px; }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
      gap: 14px 16px;
    }
    .field { display: flex; flex-direction: column; gap: 6px; }
    label { color: var(--muted); font-size: 13.5px; font-weight: 600; }
    input, select, button { font: inherit; }
    input, select {
      width: 100%;
      min-height: 40px;
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      color: var(--ink);
    }
    input::placeholder { color: var(--faint); }
    input:hover, select:hover { border-color: #9aa8b5; }
    input:focus, select:focus {
      border-color: var(--action);
      outline: 2px solid var(--wash);
      outline-offset: 0;
    }
    input[readonly] { background: var(--bg); color: var(--muted); }

    button {
      min-height: 40px;
      padding: 8px 18px;
      border: 1px solid var(--action);
      border-radius: var(--radius);
      background: var(--action);
      color: #fff;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
    }
    button:hover { background: var(--action-hover); border-color: var(--action-hover); }
    button:disabled { opacity: 0.55; cursor: wait; }
    .btn-sub { background: #fff; color: var(--action); border-color: var(--line); }
    .btn-sub:hover { background: var(--tint); border-color: var(--action); }

    .line { margin-top: 16px; display: flex; gap: 8px; align-items: center; }
    .search-box { display: flex; gap: 8px; margin-bottom: 14px; }
    .search-box input { flex: 1; }

    .link-btn {
      display: inline-block;
      padding: 4px 11px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      color: var(--action);
      font-size: 13.5px;
      font-weight: 600;
      text-decoration: none;
    }
    .link-btn:hover { background: var(--tint); border-color: var(--action); }
    .link-all { font-size: 13.5px; font-weight: 600; text-decoration: none; }
    .link-all:hover { text-decoration: underline; }

    .pager {
      margin-top: 16px;
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      font-size: 14px;
      font-variant-numeric: tabular-nums;
    }
    .muted { color: var(--muted); }
    .hint { margin: 0; color: var(--muted); }

    .chat-shell {
      height: calc(100vh - 150px);
      min-height: 520px;
      display: grid;
      grid-template-rows: auto 1fr auto;
      overflow: hidden;
      padding: 0;
    }
    .chat-guide { padding: 16px 20px; border-bottom: 1px solid var(--line-soft); background: var(--tint); }
    .chat-guide p { margin: 4px 0 12px; color: var(--muted); }
    .chat-examples { display: flex; flex-wrap: wrap; gap: 6px; }
    .chat-example {
      min-height: 0;
      padding: 5px 11px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      color: var(--action);
      font-size: 13.5px;
      font-weight: 600;
    }
    .chat-example:hover { background: var(--wash); border-color: var(--action); }
    .chat-messages { overflow-y: auto; padding: 20px; background: var(--bg); }
    .chat-message { display: flex; margin-bottom: 12px; }
    .chat-message.user { justify-content: flex-end; }
    .chat-bubble {
      max-width: min(780px, 88%);
      padding: 10px 14px;
      border-radius: 4px;
      line-height: 1.6;
      overflow-wrap: anywhere;
    }
    .chat-message.agent .chat-bubble {
      border: 1px solid var(--line);
      background: var(--surface);
    }
    .chat-message.user .chat-bubble {
      background: var(--action);
      color: #fff;
    }
    .chat-bubble p { margin: 0 0 8px; }
    .chat-bubble p:last-child { margin-bottom: 0; }
    .chat-bubble code {
      padding: 1px 5px;
      border-radius: var(--radius);
      background: var(--wash);
      color: var(--deep);
      font-family: Consolas, "D2Coding", monospace;
      font-size: 0.92em;
    }
    .chat-message.user .chat-bubble code {
      background: rgba(255, 255, 255, 0.18);
      color: #fff;
    }
    .chat-table-wrap { overflow-x: auto; margin-top: 10px; }
    .chat-input {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      padding: 12px 14px;
      border-top: 1px solid var(--line-soft);
      background: var(--surface);
    }
    .chat-input input { min-width: 0; }

    .login-form { max-width: 360px; }
    .edit-form { display: flex; gap: 8px; align-items: center; }
    .edit-form input[type="text"] { min-width: 180px; }
    .edit-form input[type="number"] { width: 96px; }
    .edit-form button { min-height: 36px; padding: 5px 14px; }

    @media (max-width: 900px) {
      .layout { grid-template-columns: 1fr; }
      .sidebar { position: static; height: auto; padding: 18px 14px 12px; border-right: 0; border-bottom: 1px solid var(--line-soft); }
      .brand { padding-bottom: 12px; }
      .nav { display: flex; flex-wrap: wrap; gap: 4px; }
      .nav a { border-left: 0; border-radius: var(--radius); margin: 0; padding: 8px 12px; }
      .nav a.active { box-shadow: inset 0 -2px 0 var(--action); }
      .group-title { flex: 0 0 100%; margin: 10px 4px 2px; }
      .admin { margin-top: 14px; }
      .main { padding: 20px 16px 40px; }
      .stats { grid-template-columns: 1fr; }
      .stat + .stat { border-left: 0; border-top: 1px solid var(--line-soft); }
      .cards { grid-template-columns: 1fr; }
      .chat-shell { height: 72vh; }
    }
    @media (prefers-reduced-motion: reduce) {
      * { transition: none !important; }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <a class="brand" href="{{ url_for('dashboard') }}">
        <span class="brand-mark" aria-hidden="true"></span>
        <span>
          <span class="brand-name">Stockroom</span><br />
          <span class="brand-sub">소형창고 재고관리</span>
        </span>
      </a>

      <nav class="nav" aria-label="주 메뉴">
        <a href="{{ url_for('dashboard') }}" class="{{ 'active' if active == 'dashboard' else '' }}">대시보드</a>

        <div class="group-title">등록</div>
        <a href="{{ url_for('product_register') }}" class="{{ 'active' if active == 'product' else '' }}">품목 등록</a>
        <a href="{{ url_for('movement_register') }}" class="{{ 'active' if active == 'movement' else '' }}">입출고 등록</a>

        <div class="group-title">조회</div>
        <a href="{{ url_for('inventory_status') }}" class="{{ 'active' if active == 'inventory' else '' }}">재고 현황</a>
        <a href="{{ url_for('product_history') }}" class="{{ 'active' if active == 'history' else '' }}">품목별 입출고 현황</a>

        <div class="group-title">AI 도우미</div>
        <a href="{{ url_for('chat') }}" class="{{ 'active' if active == 'chat' else '' }}">대화창</a>
      </nav>

      <div class="admin">
        {% if session.get('is_admin') %}
          <span class="who">관리자 로그인됨</span>
          <div class="links">
            <a href="{{ url_for('admin_manage') }}">관리자 설정</a>
            <a href="{{ url_for('admin_logout') }}">로그아웃</a>
          </div>
        {% else %}
          <a href="{{ url_for('admin_login') }}">관리자 로그인</a>
        {% endif %}
      </div>
    </aside>
    <main class="main">
      <div class="head-row">
        <h1>{{ page_title }}</h1>
        <span class="date">{{ today }}</span>
      </div>
      {% if message %}
      <div class="flash" role="status">{{ message }}</div>
      {% endif %}
      {{ content|safe }}
    </main>
  </div>
</body>
</html>
"""


def render_page(
    *,
    title: str,
    page_title: str,
    active: str,
    content: str,
    message: str = "",
    **context: Any,
) -> str:
    return render_template_string(
        BASE_TEMPLATE,
        title=title,
        page_title=page_title,
        active=active,
        content=render_template_string(content, **context),
        today=today_iso(),
        message=message,
        session=session,
        url_for=url_for,
    )


@app.before_request
def before_request() -> None:
    init_db()


@app.route("/")
def dashboard() -> str:
    db = get_db()
    low_stock = db.execute(
        """
        SELECT
            p.registered_date, c.name AS category_name, p.name AS product_name, p.minimum_stock,
            COALESCE(SUM(CASE WHEN m.movement_type = '입고' THEN m.quantity ELSE -m.quantity END), 0) AS current_stock
        FROM products p
        JOIN categories c ON c.id = p.category_id
        LEFT JOIN movements m ON m.product_id = p.id
        GROUP BY p.id
        HAVING current_stock <= p.minimum_stock
        ORDER BY current_stock ASC, p.name ASC
        LIMIT 5
        """
    ).fetchall()

    recent_movements = db.execute(
        """
        SELECT
            m.id, c.name AS category_name, p.name AS product_name, m.movement_type, m.quantity
        FROM movements m
        JOIN products p ON p.id = m.product_id
        JOIN categories c ON c.id = p.category_id
        ORDER BY m.id DESC
        LIMIT 5
        """
    ).fetchall()

    summary = db.execute(
        """
        SELECT
            COUNT(*) AS product_count,
            COALESCE(SUM(stock), 0) AS total_stock,
            COALESCE(SUM(CASE WHEN stock <= minimum_stock THEN 1 ELSE 0 END), 0) AS low_count
        FROM (
            SELECT
                p.minimum_stock,
                COALESCE(SUM(CASE WHEN m.movement_type = '입고' THEN m.quantity ELSE -m.quantity END), 0) AS stock
            FROM products p
            LEFT JOIN movements m ON m.product_id = p.id
            GROUP BY p.id
        )
        """
    ).fetchone()

    content = """
    <div class="stats">
      <div class="stat">
        <div class="stat-label">등록 품목</div>
        <div class="stat-value">{{ '{:,}'.format(summary['product_count']) }}<small>개</small></div>
      </div>
      <div class="stat {{ 'is-alert' if summary['low_count'] else '' }}">
        <div class="stat-label">재고 부족 품목</div>
        <div class="stat-value">{{ '{:,}'.format(summary['low_count']) }}<small>개</small></div>
      </div>
      <div class="stat">
        <div class="stat-label">전체 재고 수량</div>
        <div class="stat-value">{{ '{:,}'.format(summary['total_stock']) }}<small>개</small></div>
      </div>
    </div>

    <div class="cards">
      <section class="card">
        <div class="card-head">
          <h3>재고 부족 품목</h3>
          <a class="link-all" href="{{ url_for('inventory_status') }}">재고 현황 보기</a>
        </div>
        <table>
          <thead><tr><th>등록일자</th><th>분류</th><th>제품명</th><th class="num">최소재고</th><th class="num">현재고</th></tr></thead>
          <tbody>
          {% for row in low_stock %}
            <tr class="is-low">
              <td>{{ row['registered_date'] }}</td>
              <td>{{ row['category_name'] }}</td>
              <td class="name">{{ row['product_name'] }}</td>
              <td class="num">{{ row['minimum_stock'] }}</td>
              <td class="num low-text">{{ row['current_stock'] }}</td>
            </tr>
          {% else %}
            <tr><td colspan="5" class="empty">재고 부족 품목이 없습니다.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </section>
      <section class="card">
        <div class="card-head">
          <h3>최근 입출고</h3>
          <span class="card-note">최근 5건</span>
        </div>
        <table>
          <thead><tr><th class="num">순번</th><th>분류</th><th>제품명</th><th>구분</th><th class="num">수량</th></tr></thead>
          <tbody>
          {% for row in recent_movements %}
            <tr>
              <td class="num">{{ row['id'] }}</td>
              <td>{{ row['category_name'] }}</td>
              <td class="name">{{ row['product_name'] }}</td>
              <td><span class="pill {{ 'in' if row['movement_type'] == '입고' else 'out' }}">{{ row['movement_type'] }}</span></td>
              <td class="num">{{ row['quantity'] }}</td>
            </tr>
          {% else %}
            <tr><td colspan="5" class="empty">입출고 내역이 없습니다.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </section>
    </div>
    """

    return render_page(
        title="재고 관리",
        page_title="재고 관리",
        active="dashboard",
        content=content,
        low_stock=low_stock,
        recent_movements=recent_movements,
        summary=summary,
    )


@app.route("/products/register", methods=["GET", "POST"])
def product_register() -> str:
    db = get_db()
    message = ""
    if request.method == "POST":
        registered_date = request.form.get("registered_date", today_iso()).strip()
        category_id = request.form.get("category_id", "").strip()
        name = request.form.get("name", "").strip()
        initial_qty = int(request.form.get("initial_qty", "0"))
        minimum_stock = int(request.form.get("minimum_stock", "0"))

        if not (category_id and name):
            message = "분류와 제품명을 입력해 주세요."
        elif initial_qty < 0 or minimum_stock < 0:
            message = "수량은 0 이상이어야 합니다."
        else:
            try:
                cur = db.execute(
                    """
                    INSERT INTO products(registered_date, category_id, name, minimum_stock)
                    VALUES (?, ?, ?, ?)
                    """,
                    (registered_date, int(category_id), name, minimum_stock),
                )
                product_id = cur.lastrowid
                if initial_qty > 0:
                    db.execute(
                        """
                        INSERT INTO movements(movement_date, product_id, movement_type, quantity)
                        VALUES (?, ?, '입고', ?)
                        """,
                        (registered_date, product_id, initial_qty),
                    )
                db.commit()
                return redirect(url_for("product_register", ok=1))
            except sqlite3.IntegrityError:
                message = "이미 등록된 제품명입니다."

    if request.args.get("ok"):
        message = "품목 등록이 완료되었습니다."

    products = db.execute(
        """
        SELECT p.id, p.registered_date, p.name, p.minimum_stock, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        ORDER BY p.id DESC
        LIMIT 10
        """
    ).fetchall()
    stocks = get_stock_map()

    content = """
    <section class="card">
      <h3>새 품목 정보</h3>
      <form method="post">
        <div class="form-grid">
          <div class="field">
            <label>등록일자</label>
            <input type="date" name="registered_date" value="{{ today }}" required />
          </div>
          <div class="field">
            <label>분류</label>
            <select name="category_id" required>
              <option value="">선택</option>
              {% for c in categories %}
                <option value="{{ c['id'] }}">{{ c['name'] }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="field">
            <label>제품명</label>
            <input type="text" name="name" placeholder="제품명" required />
          </div>
          <div class="field">
            <label>초기수량</label>
            <input type="number" min="0" name="initial_qty" value="0" required />
          </div>
          <div class="field">
            <label>최소 재고량</label>
            <input type="number" min="0" name="minimum_stock" value="0" required />
          </div>
        </div>
        <div class="line"><button type="submit">등록</button></div>
      </form>
    </section>

    <section class="card">
      <div class="card-head">
        <h3>최근 등록 품목</h3>
        <span class="card-note">최근 10건</span>
      </div>
      <table>
        <thead><tr><th class="num">순번</th><th>등록일자</th><th>분류</th><th>제품명</th><th class="num">재고량</th><th class="num">최소재고</th></tr></thead>
        <tbody>
        {% for p in products %}
          <tr class="{{ 'is-low' if stocks.get(p['id'], 0) <= p['minimum_stock'] else '' }}">
            <td class="num">{{ p['id'] }}</td>
            <td>{{ p['registered_date'] }}</td>
            <td>{{ p['category_name'] }}</td>
            <td class="name">{{ p['name'] }}</td>
            <td class="num">{{ stocks.get(p['id'], 0) }}</td>
            <td class="num">{{ p['minimum_stock'] }}</td>
          </tr>
        {% else %}
          <tr><td colspan="6" class="empty">등록된 품목이 없습니다.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </section>
    """

    return render_page(
        title="품목 등록",
        page_title="품목 등록",
        active="product",
        content=content,
        categories=get_categories(),
        products=products,
        stocks=stocks,
        today=today_iso(),
        message=message,
    )


@app.route("/movements/register", methods=["GET", "POST"])
def movement_register() -> str:
    db = get_db()
    message = ""
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", "1"))
    selected_product_id = int(request.args.get("product_id", "0") or "0")

    if request.method == "POST":
        selected_product_id = int(request.form.get("product_id", "0"))
        movement_date = request.form.get("movement_date", today_iso()).strip()
        movement_type = request.form.get("movement_type", "").strip()
        quantity = int(request.form.get("quantity", "0"))
        product = find_product(selected_product_id)
        if not product:
            message = "제품을 선택해 주세요."
        elif movement_type not in ("입고", "출고"):
            message = "입출고 유형이 올바르지 않습니다."
        elif quantity <= 0:
            message = "수량은 1 이상이어야 합니다."
        else:
            current_stock = get_stock_map().get(selected_product_id, 0)
            if movement_type == "출고" and quantity > current_stock:
                message = f"현재고({current_stock})보다 많이 출고할 수 없습니다."
            else:
                db.execute(
                    """
                    INSERT INTO movements(movement_date, product_id, movement_type, quantity)
                    VALUES (?, ?, ?, ?)
                    """,
                    (movement_date, selected_product_id, movement_type, quantity),
                )
                db.commit()
                return redirect(
                    url_for("movement_register", q=q, page=page, product_id=selected_product_id, ok=1)
                )

    if request.args.get("ok"):
        message = "입출고 등록이 완료되었습니다."

    where_sql = ""
    args: tuple[Any, ...] = ()
    if q:
        where_sql = "WHERE p.name LIKE ?"
        args = (f"%{q}%",)

    count = db.execute(f"SELECT COUNT(*) FROM products p {where_sql}", args).fetchone()[0]
    pg = paginate(count, page)
    products = db.execute(
        f"""
        SELECT p.id, p.registered_date, p.name, p.minimum_stock, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        {where_sql}
        ORDER BY p.id ASC
        LIMIT ? OFFSET ?
        """,
        args + (pg["per_page"], pg["offset"]),
    ).fetchall()
    selected = find_product(selected_product_id) if selected_product_id else None
    stocks = get_stock_map()

    content = """
    <section class="card">
      <h3>1. 제품 선택</h3>
      <form class="search-box" method="get">
        <input type="text" name="q" value="{{ q }}" placeholder="제품명을 검색하세요" aria-label="제품명 검색" />
        <button type="submit">검색</button>
      </form>
      <table>
        <thead><tr><th class="num">순번</th><th>등록일자</th><th>분류</th><th>제품명</th><th class="num">현재고</th><th></th></tr></thead>
        <tbody>
        {% for p in products %}
          <tr class="{{ 'is-selected' if p['id'] == selected_id else '' }}">
            <td class="num">{{ p['id'] }}</td>
            <td>{{ p['registered_date'] }}</td>
            <td>{{ p['category_name'] }}</td>
            <td class="name">{{ p['name'] }}</td>
            <td class="num">{{ stocks.get(p['id'], 0) }}</td>
            <td class="num"><a class="link-btn" href="{{ url_for('movement_register', q=q, page=page, product_id=p['id']) }}">{{ '선택됨' if p['id'] == selected_id else '선택' }}</a></td>
          </tr>
        {% else %}
          <tr><td colspan="6" class="empty">조회 결과가 없습니다.</td></tr>
        {% endfor %}
        </tbody>
      </table>
      <div class="pager">
        {% if page > 1 %}
          <a class="link-btn" href="{{ url_for('movement_register', q=q, page=page-1, product_id=selected_id) }}">이전</a>
        {% endif %}
        <span>{{ page }} / {{ pages }}</span>
        {% if page < pages %}
          <a class="link-btn" href="{{ url_for('movement_register', q=q, page=page+1, product_id=selected_id) }}">다음</a>
        {% endif %}
      </div>
    </section>

    <section class="card">
      <h3>2. 입출고 등록</h3>
      {% if selected %}
        <form method="post">
          <input type="hidden" name="product_id" value="{{ selected['id'] }}" />
          <div class="form-grid">
            <div class="field">
              <label>등록일자</label>
              <input type="date" name="movement_date" value="{{ today }}" required />
            </div>
            <div class="field">
              <label>분류</label>
              <input type="text" value="{{ selected['category_name'] }}" readonly />
            </div>
            <div class="field">
              <label>제품명</label>
              <input type="text" value="{{ selected['name'] }}" readonly />
            </div>
            <div class="field">
              <label>입출고</label>
              <select name="movement_type" required>
                <option value="입고">입고</option>
                <option value="출고">출고</option>
              </select>
            </div>
            <div class="field">
              <label>수량</label>
              <input type="number" min="1" name="quantity" required />
            </div>
            <div class="field">
              <label>현재고</label>
              <input type="text" value="{{ stocks.get(selected['id'], 0) }}" readonly />
            </div>
          </div>
          <div class="line"><button type="submit">입출고 등록</button></div>
        </form>
      {% else %}
        <p class="hint">위 목록에서 제품을 선택하면 입력 양식이 나타납니다.</p>
      {% endif %}
    </section>
    """

    return render_page(
        title="입출고 등록",
        page_title="입출고 등록",
        active="movement",
        content=content,
        q=q,
        page=pg["page"],
        pages=pg["pages"],
        products=products,
        selected=selected,
        selected_id=selected_product_id,
        stocks=stocks,
        today=today_iso(),
        message=message,
    )


@app.route("/inventory")
def inventory_status() -> str:
    db = get_db()
    page = int(request.args.get("page", "1"))
    rows = db.execute(
        """
        SELECT
            p.id, p.name, p.registered_date, p.minimum_stock, c.name AS category_name,
            MAX(m.movement_date) AS recent_movement_date,
            COALESCE(SUM(CASE WHEN m.movement_type = '입고' THEN m.quantity ELSE -m.quantity END), 0) AS stock
        FROM products p
        JOIN categories c ON c.id = p.category_id
        LEFT JOIN movements m ON m.product_id = p.id
        GROUP BY p.id
        ORDER BY stock ASC, p.id ASC
        """
    ).fetchall()

    total = len(rows)
    pg = paginate(total, page)
    sliced = rows[pg["offset"] : pg["offset"] + pg["per_page"]]

    content = """
    <section class="card bg-blue">
      <h3>재고 현황 (재고량 적은 순)</h3>
      <table>
        <thead><tr><th>순번</th><th>최근 입출고 일자</th><th>분류</th><th>제품명</th><th>재고량</th><th>최소 재고량</th><th>상태</th></tr></thead>
        <tbody>
        {% for r in rows %}
          <tr>
            <td>{{ r['id'] }}</td>
            <td>{{ r['recent_movement_date'] or '-' }}</td>
            <td>{{ r['category_name'] }}</td>
            <td>{{ r['name'] }}</td>
            <td class="{{ 'danger' if r['stock'] <= r['minimum_stock'] else '' }}">{{ r['stock'] }}</td>
            <td>{{ r['minimum_stock'] }}</td>
            <td>
              {% if r['stock'] <= r['minimum_stock'] %}
                <span class="pill" style="background:#ffe8e2;color:#b6472e;">부족</span>
              {% else %}
                <span class="pill" style="background:#e6f7ed;color:#237447;">정상</span>
              {% endif %}
            </td>
          </tr>
        {% else %}
          <tr><td colspan="7" class="muted">등록된 재고가 없습니다.</td></tr>
        {% endfor %}
        </tbody>
      </table>
      <div class="pager">
        {% if page > 1 %}
          <a href="{{ url_for('inventory_status', page=page-1) }}">이전</a>
        {% endif %}
        <span>{{ page }} / {{ pages }}</span>
        {% if page < pages %}
          <a href="{{ url_for('inventory_status', page=page+1) }}">다음</a>
        {% endif %}
      </div>
    </section>
    """

    return render_page(
        title="재고 현황",
        page_title="재고 현황",
        active="inventory",
        content=content,
        rows=sliced,
        page=pg["page"],
        pages=pg["pages"],
    )


@app.route("/history")
def product_history() -> str:
    db = get_db()
    q = request.args.get("q", "").strip()
    product_id = int(request.args.get("product_id", "0") or "0")
    page = int(request.args.get("page", "1"))

    where_sql = ""
    args: tuple[Any, ...] = ()
    if q:
        where_sql = "WHERE p.name LIKE ?"
        args = (f"%{q}%",)

    count = db.execute(f"SELECT COUNT(*) FROM products p {where_sql}", args).fetchone()[0]
    pg = paginate(count, page)
    products = db.execute(
        f"""
        SELECT p.id, p.registered_date, p.name, p.minimum_stock, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        {where_sql}
        ORDER BY p.id ASC
        LIMIT ? OFFSET ?
        """,
        args + (pg["per_page"], pg["offset"]),
    ).fetchall()
    stocks = get_stock_map()
    selected = find_product(product_id) if product_id else None

    history_rows: list[sqlite3.Row] = []
    if selected:
        history_rows = db.execute(
            """
            SELECT m.id, m.movement_date, c.name AS category_name, p.name AS product_name, m.movement_type, m.quantity
            FROM movements m
            JOIN products p ON p.id = m.product_id
            JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?
            ORDER BY m.id ASC
            """,
            (selected["id"],),
        ).fetchall()

    running = 0
    history_with_stock: list[dict[str, Any]] = []
    for row in history_rows:
        if row["movement_type"] == "입고":
            running += row["quantity"]
        else:
            running -= row["quantity"]
        history_with_stock.append({**dict(row), "stock_after": running})

    content = """
    <section class="card bg-blue">
      <h3>품목 검색</h3>
      <form class="search-box" method="get">
        <input type="text" name="q" value="{{ q }}" placeholder="제품명을 검색하세요" />
        <button type="submit">검색</button>
      </form>
      <table>
        <thead><tr><th>순번</th><th>등록일자</th><th>분류</th><th>제품명</th><th>현재고</th><th>선택</th></tr></thead>
        <tbody>
        {% for p in products %}
          <tr>
            <td>{{ p['id'] }}</td>
            <td>{{ p['registered_date'] }}</td>
            <td>{{ p['category_name'] }}</td>
            <td>{{ p['name'] }}</td>
            <td>{{ stocks.get(p['id'], 0) }}</td>
            <td><a href="{{ url_for('product_history', q=q, page=page, product_id=p['id']) }}">보기</a></td>
          </tr>
        {% else %}
          <tr><td colspan="6" class="muted">조회 결과가 없습니다.</td></tr>
        {% endfor %}
        </tbody>
      </table>
      <div class="pager">
        {% if page > 1 %}
          <a href="{{ url_for('product_history', q=q, page=page-1, product_id=selected_id) }}">이전</a>
        {% endif %}
        <span>{{ page }} / {{ pages }}</span>
        {% if page < pages %}
          <a href="{{ url_for('product_history', q=q, page=page+1, product_id=selected_id) }}">다음</a>
        {% endif %}
      </div>
    </section>

    <section class="card bg-orange" style="margin-top:14px;">
      <h3>품목별 입출고 내역</h3>
      {% if selected %}
        <p class="muted"><strong>{{ selected['name'] }}</strong> / 분류 {{ selected['category_name'] }}</p>
        <table>
          <thead><tr><th>순번</th><th>등록일자</th><th>분류</th><th>제품명</th><th>입고/출고</th><th>수량</th><th>재고량</th></tr></thead>
          <tbody>
          {% for row in history_rows %}
            <tr>
              <td>{{ row['id'] }}</td>
              <td>{{ row['movement_date'] }}</td>
              <td>{{ row['category_name'] }}</td>
              <td>{{ row['product_name'] }}</td>
              <td>{{ row['movement_type'] }}</td>
              <td>{{ row['quantity'] }}</td>
              <td>{{ row['stock_after'] }}</td>
            </tr>
          {% else %}
            <tr><td colspan="7" class="muted">입출고 내역이 없습니다.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      {% else %}
        <p class="muted">상단에서 제품을 선택해 주세요.</p>
      {% endif %}
    </section>
    """

    return render_page(
        title="품목별 입출고 현황",
        page_title="품목별 입출고 현황",
        active="history",
        content=content,
        q=q,
        products=products,
        stocks=stocks,
        page=pg["page"],
        pages=pg["pages"],
        selected=selected,
        selected_id=product_id,
        history_rows=history_with_stock,
    )


@app.route("/chat")
def chat() -> str:
    content = """
    <section class="card chat-shell">
      <div class="chat-guide">
        <strong>자연어로 재고를 관리하세요</strong>
        <p>입출고 등록, 재고 조회, 신규 제품 등록과 발주 메일 발송을 요청할 수 있습니다.</p>
        <div class="chat-examples">
          <button type="button" class="chat-example" data-message="최소 재고량 이하 제품 알려줘">재고 부족 조회</button>
          <button type="button" class="chat-example" data-message="재고 10개 이하 제품 목록 보여줘">10개 이하 조회</button>
          <button type="button" class="chat-example" data-message="신규 제품 등록">신규 제품 등록</button>
        </div>
      </div>
      <div id="chat-messages" class="chat-messages" aria-live="polite">
        <div class="chat-message agent">
          <div class="chat-bubble">
            <p>안녕하세요. 재고관리 도우미입니다.</p>
            <p>예: <code>USB-C 케이블 10개 입고</code></p>
          </div>
        </div>
      </div>
      <form id="chat-form" class="chat-input">
        <input id="chat-message" type="text" maxlength="500" autocomplete="off"
               placeholder="재고관리 요청을 입력하세요" aria-label="재고관리 요청" required />
        <button id="chat-submit" type="submit">전송</button>
      </form>
    </section>
    <script>
      (() => {
        const form = document.getElementById("chat-form");
        const input = document.getElementById("chat-message");
        const submit = document.getElementById("chat-submit");
        const messages = document.getElementById("chat-messages");

        function appendMessage(role, value, isHtml = false) {
          const row = document.createElement("div");
          row.className = `chat-message ${role}`;
          const bubble = document.createElement("div");
          bubble.className = "chat-bubble";
          if (isHtml) bubble.innerHTML = value;
          else bubble.textContent = value;
          row.appendChild(bubble);
          messages.appendChild(row);
          messages.scrollTop = messages.scrollHeight;
        }

        async function sendMessage(message) {
          const clean = message.trim();
          if (!clean || submit.disabled) return;
          appendMessage("user", clean);
          input.value = "";
          submit.disabled = true;
          submit.textContent = "처리 중";

          try {
            const response = await fetch("{{ url_for('chat_api') }}", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ message: clean })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "요청 처리에 실패했습니다.");
            appendMessage("agent", data.answer_html, true);
          } catch (error) {
            appendMessage("agent", error.message || "서버 연결에 실패했습니다.");
          } finally {
            submit.disabled = false;
            submit.textContent = "전송";
            input.focus();
          }
        }

        form.addEventListener("submit", (event) => {
          event.preventDefault();
          sendMessage(input.value);
        });
        document.querySelectorAll(".chat-example").forEach((button) => {
          button.addEventListener("click", () => sendMessage(button.dataset.message));
        });
      })();
    </script>
    """
    return render_page(
        title="대화창",
        page_title="대화창",
        active="chat",
        content=content,
    )


@app.post("/api/chat")
def chat_api() -> Any:
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"error": "메시지를 입력해 주세요."}), 400
    if len(message) > 500:
        return jsonify({"error": "메시지는 500자 이하로 입력해 주세요."}), 400

    try:
        effective_message = message
        if session.get("chat_pending") == "register_product" and (
            "분류" in message or "제품명" in message or "최소재고" in message.replace(" ", "")
        ):
            effective_message = f"신규 제품 등록, {message}"

        result = inventory_agent.invoke(effective_message)
        action = result.pop("action")
        if (
            action["intent"] == "register_product"
            and not result["success"]
            and (
                not action.get("category")
                or not action.get("product_name")
                or action.get("minimum_stock") is None
            )
        ):
            session["chat_pending"] = "register_product"
        else:
            session.pop("chat_pending", None)
        return jsonify(result)
    except Exception:
        app.logger.exception("재고 에이전트 요청 처리 실패")
        return jsonify({"error": "에이전트 요청 처리 중 오류가 발생했습니다."}), 500


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login() -> str:
    message = ""
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_manage"))
        message = "비밀번호가 올바르지 않습니다."

    content = """
    <section class="card bg-blue">
      <h3>관리자 로그인</h3>
      <form method="post">
        <div class="field" style="max-width:340px;">
          <label>비밀번호</label>
          <input type="password" name="password" required />
        </div>
        <div class="line"><button type="submit">로그인</button></div>
      </form>
      <p class="muted">기본 비밀번호: admin1004</p>
    </section>
    """
    return render_page(
        title="관리자 로그인",
        page_title="관리자 로그인",
        active="admin",
        content=content,
        message=message,
    )


@app.route("/admin/logout")
def admin_logout() -> Any:
    session.pop("is_admin", None)
    return redirect(url_for("dashboard"))


@app.route("/admin/manage", methods=["GET", "POST"])
def admin_manage() -> str:
    require_admin()
    db = get_db()
    message = ""

    if request.method == "POST":
        action = request.form.get("action", "").strip()
        if action == "add_category":
            category_name = request.form.get("category_name", "").strip()
            if category_name:
                try:
                    db.execute("INSERT INTO categories(name) VALUES (?)", (category_name,))
                    db.commit()
                    message = "분류가 추가되었습니다."
                except sqlite3.IntegrityError:
                    message = "이미 존재하는 분류입니다."
        elif action == "edit_product":
            product_id = int(request.form.get("product_id", "0"))
            new_name = request.form.get("new_name", "").strip()
            minimum_stock = int(request.form.get("minimum_stock", "0"))
            if product_id and new_name and minimum_stock >= 0:
                try:
                    db.execute(
                        "UPDATE products SET name = ?, minimum_stock = ? WHERE id = ?",
                        (new_name, minimum_stock, product_id),
                    )
                    db.commit()
                    message = "제품 정보가 수정되었습니다."
                except sqlite3.IntegrityError:
                    message = "이미 존재하는 제품명입니다."

    products = db.execute(
        """
        SELECT p.id, p.name, p.minimum_stock, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        ORDER BY p.id ASC
        """
    ).fetchall()

    content = """
    <section class="card bg-green">
      <h3>분류 추가</h3>
      <form method="post">
        <input type="hidden" name="action" value="add_category" />
        <div class="line">
          <input type="text" name="category_name" placeholder="새 분류명" required />
          <button type="submit">추가</button>
        </div>
      </form>
    </section>

    <section class="card bg-orange" style="margin-top:14px;">
      <h3>제품명 / 최소재고 수정</h3>
      <table>
        <thead><tr><th>순번</th><th>분류</th><th>제품명</th><th>최소재고</th><th>수정</th></tr></thead>
        <tbody>
        {% for p in products %}
          <tr>
            <td>{{ p['id'] }}</td>
            <td>{{ p['category_name'] }}</td>
            <td>{{ p['name'] }}</td>
            <td>{{ p['minimum_stock'] }}</td>
            <td>
              <form method="post" style="display:flex;gap:6px;">
                <input type="hidden" name="action" value="edit_product" />
                <input type="hidden" name="product_id" value="{{ p['id'] }}" />
                <input type="text" name="new_name" value="{{ p['name'] }}" required />
                <input type="number" min="0" name="minimum_stock" value="{{ p['minimum_stock'] }}" required style="width:90px;" />
                <button type="submit">저장</button>
              </form>
            </td>
          </tr>
        {% else %}
          <tr><td colspan="5" class="muted">등록된 제품이 없습니다.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </section>
    """
    return render_page(
        title="관리자 설정",
        page_title="관리자 설정",
        active="admin",
        content=content,
        products=products,
        message=message,
    )


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
        exclude_patterns=[
            os.path.join(sys.base_prefix, "*"),
            os.path.join(sys.prefix, "Lib", "*"),
        ],
    )
