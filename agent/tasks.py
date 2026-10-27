"""Benign agent tasks.

Simple explanation
------------------
A *task* is something a user might ask the agent to do ("summarise my notes").
Each task carries two descriptions of the same intent:

* ``prompt`` -- natural language, given to a **real LLM**, which decides on its
  own which tools to call.
* ``plan`` -- an ordered list of tool steps followed by the **mock LLM**. Steps
  can be optional (probability ``p``) and can pick their arguments at random
  from ``choices``. With a fixed seed the mock is fully reproducible; across
  seeds it produces *varied* benign traffic (different files, extra exploratory
  calls, occasional natural errors such as a missing file).

Why variation matters: if every benign session were byte-identical, a classifier
could learn "anything that isn't exactly this is an attack" -- a useless IDS.

Tool names in plans are *namespaced* ``<server_id>__<tool>`` -- the same names
the driver exposes to the LLM (see :mod:`agent.driver`).

``{web}`` in prompts or plan arguments is replaced at run time with the test
site's base URL (``http://testweb:8080`` in Docker, a local port otherwise);
see :func:`render_task`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class PlanStep:
    tool: str
    choices: tuple[dict[str, Any], ...] = ({},)
    p: float = 1.0                       # probability the step is executed
    on_error: dict[str, Any] | None = None  # retry args if the call errors
    if_previous: bool = False            # skip if the previous step was skipped (e.g. paging)


@dataclass(frozen=True)
class Task:
    task_id: str
    prompt: str
    servers: tuple[str, ...]
    plan: tuple[PlanStep, ...] = field(default_factory=tuple)


FS = "filesystem__"
DB = "sqlite__"
WEB = "web_fetch__"
CALC = "calculator__"
SHADOW = "shadowing_control__"
SAMPLING = "sampling_control__"
WRITE = "writing_assistant__"
HELP = "helpdesk__"

TASKS: dict[str, Task] = {t.task_id: t for t in [
    Task(
        task_id="fs_summarize_notes",
        prompt="Read my notes file in the workspace and give me a short summary of it.",
        servers=("filesystem",),
        plan=(
            PlanStep(FS + "list_directory", ({"path": "."},), p=0.7),
            PlanStep(FS + "read_file", ({"path": "notes.txt"}, {"path": "Notes.txt"}),
                     on_error={"path": "notes.txt"}),
        ),
    ),
    Task(
        task_id="fs_find_data_files",
        prompt="Find the sample data files in the workspace and tell me what fields the CSV has.",
        servers=("filesystem",),
        plan=(
            PlanStep(FS + "search_files", ({"pattern": "sample"}, {"pattern": ".csv"})),
            PlanStep(FS + "list_directory", ({"path": "data"},), p=0.5),
            PlanStep(FS + "read_file", ({"path": "data/sample.csv"},)),
            PlanStep(FS + "read_file", ({"path": "data/sample.json"},), p=0.4),
        ),
    ),
    Task(
        task_id="fs_report_digest",
        prompt="Read the quarterly report and save a one-line digest of it to documents/digest.txt.",
        servers=("filesystem",),
        plan=(
            PlanStep(FS + "list_directory", ({"path": "."}, {"path": "documents"}), p=0.6),
            PlanStep(FS + "read_file", ({"path": "report.txt"}, {"path": "reports/report.txt"}),
                     on_error={"path": "report.txt"}),
            PlanStep(FS + "write_file", (
                {"path": "documents/digest.txt", "content": "Synthetic revenue 174,400; East region leads."},
                {"path": "documents/digest.txt", "content": "Digest: four regions, total 174,400 (synthetic)."},
            )),
            PlanStep(FS + "read_file", ({"path": "documents/digest.txt"},), p=0.3),
        ),
    ),
    Task(
        task_id="fs_explore_documents",
        prompt="What documents are in my workspace? Open the meeting agenda and list its items.",
        servers=("filesystem",),
        plan=(
            PlanStep(FS + "list_directory", ({"path": "documents"},)),
            PlanStep(FS + "search_files", ({"pattern": "agenda"},), p=0.5),
            PlanStep(FS + "read_file", ({"path": "documents/meeting_agenda.txt"},)),
            PlanStep(FS + "read_file", ({"path": "documents/readme.md"},), p=0.3),
        ),
    ),
    # ------------------------------------------------------------ sqlite
    Task(
        task_id="db_top_products",
        prompt="Which are the most expensive products in the shop database?",
        servers=("sqlite",),
        plan=(
            PlanStep(DB + "list_tables", p=0.6),
            PlanStep(DB + "describe_table", ({"table": "products"},), p=0.5),
            PlanStep(DB + "read_query", (
                {"sql": "SELECT name, price FROM products ORDER BY price DESC LIMIT 5"},
                {"sql": "SELECT name, category, price FROM products ORDER BY price DESC LIMIT 3"},
            )),
        ),
    ),
    Task(
        task_id="db_order_status",
        prompt="How many orders are there in each status?",
        servers=("sqlite",),
        plan=(
            PlanStep(DB + "describe_table", ({"table": "orders"},), p=0.4),
            PlanStep(DB + "read_query", (
                {"sql": "SELECT status, COUNT(*) AS n FROM orders GROUP BY status"},
                {"sql": "SELECT status, COUNT(*) AS n FROM order GROUP BY status"},  # typo -> SQL error
            ), on_error={"sql": "SELECT status, COUNT(*) AS n FROM orders GROUP BY status"}),
        ),
    ),
    Task(
        task_id="db_user_lookup",
        prompt="List the users who are based in India (country code IN).",
        servers=("sqlite",),
        plan=(
            PlanStep(DB + "list_tables", p=0.3),
            PlanStep(DB + "describe_table", ({"table": "users"},), p=0.6),
            PlanStep(DB + "read_query", (
                {"sql": "SELECT username, country FROM users WHERE country = 'IN'"},
                {"sql": "SELECT username, email FROM users WHERE country = 'IN' ORDER BY username"},
            )),
        ),
    ),
    Task(
        task_id="db_add_log",
        prompt="Add an INFO log entry saying 'weekly report generated', then show the latest log entries.",
        servers=("sqlite",),
        plan=(
            PlanStep(DB + "insert_row", (
                {"table": "logs", "values": {"ts": "2026-10-01T09:00:00Z", "level": "INFO",
                                              "message": "weekly report generated"}},
                {"table": "logs", "values": {"ts": "2026-10-01T09:00:00Z", "level": "NOTICE",
                                              "message": "weekly report generated"}},  # CHECK fails
            ), on_error={"table": "logs", "values": {"ts": "2026-10-01T09:00:00Z", "level": "INFO",
                                                      "message": "weekly report generated"}}),
            PlanStep(DB + "read_query", ({"sql": "SELECT ts, level, message FROM logs ORDER BY id DESC LIMIT 5"},),
                     p=0.7),
        ),
    ),
    Task(
        task_id="db_new_order",
        prompt="Create a pending order for user 3: two units of product 5.",
        servers=("sqlite",),
        plan=(
            PlanStep(DB + "read_query", ({"sql": "SELECT id, name, stock FROM products WHERE id = 5"},), p=0.7),
            PlanStep(DB + "insert_row", (
                {"table": "orders", "values": {"user_id": 3, "product_id": 5, "quantity": 2,
                                                "order_date": "2026-10-01", "status": "pending"}},
                {"table": "orders", "values": {"user_id": 3, "product_id": 5, "quantity": 2,
                                                "order_date": "2026-10-01", "status": "new"}},  # CHECK fails
            ), on_error={"table": "orders", "values": {"user_id": 3, "product_id": 5, "quantity": 2,
                                                        "order_date": "2026-10-01", "status": "pending"}}),
        ),
    ),
    # --------------------------------------------------------- web fetch
    Task(
        task_id="web_getting_started",
        prompt="Read the getting-started guide on the test site at {web} and summarise the steps.",
        servers=("web_fetch",),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/index.html"}, {"url": "{web}/"}), p=0.5),
            PlanStep(WEB + "fetch", ({"url": "{web}/docs/getting-started.html"},)),
        ),
    ),
    Task(
        task_id="web_news",
        prompt="What happened in the latest quarterly news on {web}?",
        servers=("web_fetch",),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/news/2026-q3.html"}, {"url": "{web}/news/latest.html"}),
                     on_error={"url": "{web}/news/2026-q3.html"}),  # latest.html is a 404
        ),
    ),
    Task(
        task_id="web_faq_long",
        prompt="Read the whole FAQ page at {web}/faq.html and tell me how many questions it has.",
        servers=("web_fetch",),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/faq.html", "max_length": 3000},
                                     {"url": "{web}/faq.html", "max_length": 4000})),
            PlanStep(WEB + "fetch", ({"url": "{web}/faq.html", "max_length": 3000, "start_index": 3000},)),
            PlanStep(WEB + "fetch", ({"url": "{web}/faq.html", "max_length": 3000, "start_index": 6000},), p=0.7, if_previous=True),
            PlanStep(WEB + "fetch", ({"url": "{web}/faq.html", "max_length": 3000, "start_index": 9000},), p=0.5, if_previous=True),
        ),
    ),
    Task(
        task_id="web_api_docs",
        prompt="Look up the API reference on {web} and list the available endpoints.",
        servers=("web_fetch",),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/docs/api-reference.html"},
                                     {"url": "{web}/docs/api.html"}),  # api.html is a 404
                     on_error={"url": "{web}/docs/api-reference.html"}),
            PlanStep(WEB + "fetch", ({"url": "{web}/about.html"},), p=0.3),
        ),
    ),
    # ----------------------------------------------- multi-server (benign)
    Task(
        task_id="multi_news_to_file",
        prompt="Read the Q3 news on {web} and save a short summary to documents/news_summary.txt.",
        servers=("web_fetch", "filesystem"),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/news/2026-q3.html"},)),
            PlanStep(FS + "list_directory", ({"path": "documents"},), p=0.4),
            PlanStep(FS + "write_file", (
                {"path": "documents/news_summary.txt",
                 "content": "Q3: revenue 174,400; new Gizmo E; faster support."},
            )),
        ),
    ),
    Task(
        task_id="multi_db_report",
        prompt="Count orders by status in the database and write the result to documents/order_report.txt.",
        servers=("sqlite", "filesystem"),
        plan=(
            PlanStep(DB + "read_query", ({"sql": "SELECT status, COUNT(*) AS n FROM orders GROUP BY status"},)),
            PlanStep(FS + "read_file", ({"path": "report.txt"},), p=0.4),
            PlanStep(FS + "write_file", (
                {"path": "documents/order_report.txt", "content": "Order counts by status (synthetic data)."},
            )),
        ),
    ),
    Task(
        task_id="multi_price_check",
        prompt=("Compare product prices on the website ({web}/products.html), in the database, "
                "and in data/sample.csv. Save the differences to documents/price_check.txt."),
        servers=("web_fetch", "sqlite", "filesystem"),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/products.html"},)),
            PlanStep(DB + "read_query", ({"sql": "SELECT name, price FROM products ORDER BY name"},)),
            PlanStep(FS + "read_file", ({"path": "data/sample.csv"},)),
            PlanStep(FS + "write_file", (
                {"path": "documents/price_check.txt", "content": "Prices differ across sources (synthetic)."},
            )),
        ),
    ),
    # -------------------------------------------------------- calculator
    Task(
        task_id="calc_add",
        prompt="What is 1234.5 plus 678.25?",
        servers=("calculator",),
        plan=(
            PlanStep(CALC + "add_numbers", ({"a": 1234.5, "b": 678.25}, {"a": 678.25, "b": 1234.5})),
        ),
    ),
    Task(
        task_id="calc_temperature",
        prompt="Convert 72 degrees Fahrenheit to Celsius.",
        servers=("calculator",),
        plan=(
            PlanStep(CALC + "convert_temperature", (
                {"value": 72, "from_unit": "F", "to_unit": "C"},
                {"value": 72, "from_unit": "Fahrenheit", "to_unit": "C"},  # bad unit -> error
            ), on_error={"value": 72, "from_unit": "F", "to_unit": "C"}),
            PlanStep(CALC + "convert_temperature", ({"value": 72, "from_unit": "F", "to_unit": "K"},), p=0.3),
        ),
    ),
    Task(
        task_id="multi_order_share",
        prompt="What percentage of all orders in the database are delivered?",
        servers=("sqlite", "calculator"),
        plan=(
            PlanStep(DB + "read_query", ({"sql": "SELECT status, COUNT(*) AS n FROM orders GROUP BY status"},)),
            PlanStep(CALC + "add_numbers", ({"a": 16, "b": 34},), p=0.5),
            PlanStep(CALC + "percentage", ({"part": 34, "whole": 80},)),
        ),
    ),
    Task(
        task_id="multi_region_share",
        prompt="Using report.txt, what share of total revenue came from the East region?",
        servers=("filesystem", "calculator"),
        plan=(
            PlanStep(FS + "read_file", ({"path": "report.txt"},)),
            PlanStep(CALC + "add_numbers", ({"a": 48000, "b": 38000},), p=0.4),
            PlanStep(CALC + "percentage", ({"part": 57200, "whole": 174400},)),
        ),
    ),
    Task(
        task_id="fs_shadowing_probe",
        prompt="Read the synthetic notes file and summarize it briefly.",
        servers=("filesystem", "shadowing_control"),
        plan=(PlanStep(FS + "read_file", ({"path": "notes.txt"},)),),
    ),
    Task(
        task_id="fs_sampling_probe",
        prompt="Read the synthetic notes, then request the lab's static summary fixture.",
        servers=("filesystem", "sampling_control"),
        plan=(
            PlanStep(FS + "read_file", ({"path": "notes.txt"},)),
            PlanStep(SAMPLING + "request_summary"),
        ),
    ),
    # ----------------------------------------- more benign variety (lab 0.9.0)
    Task(
        task_id="fs_write_todo",
        prompt="Write a short to-do list for this week into documents/todo.txt.",
        servers=("filesystem",),
        plan=(
            PlanStep(FS + "list_directory", ({"path": "documents"}, {"path": "."}), p=0.6),
            PlanStep(FS + "write_file", (
                {"path": "documents/todo.txt", "content": "1. Review lab data\n2. Update notes"},
                {"path": "documents/todo.txt", "content": "- regenerate dataset\n- read report\n- sync"},
                {"path": "documents/todo.md", "content": "# To do\n* features\n* evaluation"},
            )),
            PlanStep(FS + "read_file", ({"path": "documents/todo.txt"}, {"path": "documents/todo.md"}), p=0.5),
        ),
    ),
    Task(
        task_id="fs_search_reports",
        prompt="Which files in the workspace look like reports or notes? Open the most relevant one.",
        servers=("filesystem",),
        plan=(
            PlanStep(FS + "search_files", ({"pattern": "report"}, {"pattern": "note"}, {"pattern": "txt"},
                                           {"pattern": ".md"})),
            PlanStep(FS + "search_files", ({"pattern": "notes"}, {"pattern": "agenda"}), p=0.4),
            PlanStep(FS + "read_file", ({"path": "report.txt"}, {"path": "notes.txt"},
                                        {"path": "documents/meeting_agenda.txt"}, {"path": "reports.txt"}),
                     on_error={"path": "report.txt"}),
        ),
    ),
    Task(
        task_id="fs_copy_notes",
        prompt="Make a backup copy of notes.txt in the documents folder.",
        servers=("filesystem",),
        plan=(
            PlanStep(FS + "read_file", ({"path": "notes.txt"}, {"path": "./notes.txt"})),
            PlanStep(FS + "write_file", ({"path": "documents/notes_backup.txt", "content": "Lab notes (synthetic data) backup"},
                                         {"path": "documents/backup/notes.txt", "content": "Lab notes (synthetic data) backup"})),
            PlanStep(FS + "list_directory", ({"path": "documents"}, {"path": "documents/backup"}), p=0.5),
        ),
    ),
    Task(
        task_id="fs_json_summary",
        prompt="Summarise data/sample.json and save the summary to documents/json_summary.txt.",
        servers=("filesystem",),
        plan=(
            PlanStep(FS + "list_directory", ({"path": "data"},), p=0.5),
            PlanStep(FS + "read_file", ({"path": "data/sample.json"}, {"path": "data/samples.json"}),
                     on_error={"path": "data/sample.json"}),
            PlanStep(FS + "read_file", ({"path": "data/sample.csv"},), p=0.4),
            PlanStep(FS + "write_file", ({"path": "documents/json_summary.txt", "content": "3 records: login, view_report, logout."},
                                         {"path": "documents/json_summary.txt", "content": "Synthetic sample with three user actions."})),
        ),
    ),
    Task(
        task_id="db_low_stock",
        prompt="Which products are running low on stock?",
        servers=("sqlite",),
        plan=(
            PlanStep(DB + "describe_table", ({"table": "products"},), p=0.5),
            PlanStep(DB + "read_query", (
                {"sql": "SELECT name, stock FROM products WHERE stock < 20 ORDER BY stock"},
                {"sql": "SELECT name, stock FROM products WHERE stock < 50 ORDER BY stock"},
                {"sql": "SELECT name, category, stock FROM products WHERE stock < 100"},
                {"sql": "SELECT name, stock FROM product WHERE stock < 50"},  # typo -> error
            ), on_error={"sql": "SELECT name, stock FROM products WHERE stock < 50 ORDER BY stock"}),
            PlanStep(DB + "read_query", ({"sql": "SELECT COUNT(*) AS n FROM products WHERE stock = 0"},), p=0.4),
        ),
    ),
    Task(
        task_id="db_country_counts",
        prompt="How many users are there per country?",
        servers=("sqlite",),
        plan=(
            PlanStep(DB + "list_tables", p=0.4),
            PlanStep(DB + "read_query", (
                {"sql": "SELECT country, COUNT(*) AS n FROM users GROUP BY country"},
                {"sql": "SELECT country, COUNT(*) AS n FROM users GROUP BY country ORDER BY n DESC"},
                {"sql": "SELECT country, COUNT(id) AS users FROM users GROUP BY country ORDER BY country"},
            )),
            PlanStep(DB + "read_query", ({"sql": "SELECT COUNT(*) AS total FROM users"},), p=0.5),
        ),
    ),
    Task(
        task_id="db_error_logs",
        prompt="Show recent warnings and errors from the application logs.",
        servers=("sqlite",),
        plan=(
            PlanStep(DB + "describe_table", ({"table": "logs"}, {"table": "log"}), p=0.6,
                     on_error={"table": "logs"}),
            PlanStep(DB + "read_query", (
                {"sql": "SELECT ts, level, message FROM logs WHERE level = 'ERROR' ORDER BY ts DESC LIMIT 10"},
                {"sql": "SELECT ts, level, message FROM logs WHERE level IN ('ERROR', 'WARNING') ORDER BY ts DESC"},
                {"sql": "SELECT level, COUNT(*) AS n FROM logs GROUP BY level"},
            )),
        ),
    ),
    Task(
        task_id="db_recent_orders",
        prompt="List the most recent orders with the customer's username.",
        servers=("sqlite",),
        plan=(
            PlanStep(DB + "describe_table", ({"table": "orders"},), p=0.4),
            PlanStep(DB + "read_query", (
                {"sql": "SELECT id, order_date, status FROM orders ORDER BY order_date DESC LIMIT 5"},
                {"sql": "SELECT o.id, u.username, o.order_date FROM orders o JOIN users u ON u.id = o.user_id "
                        "ORDER BY o.order_date DESC LIMIT 10"},
                {"sql": "SELECT o.id, u.username, o.status FROM orders o JOIN users u ON u.id = o.user_id "
                        "ORDER BY o.order_date DESC LIMIT 20"},
            )),
            PlanStep(DB + "read_query", ({"sql": "SELECT status, COUNT(*) AS n FROM orders GROUP BY status"},), p=0.3),
        ),
    ),
    Task(
        task_id="web_about_team",
        prompt="Who works at Lab Widgets? Check the about page on {web}.",
        servers=("web_fetch",),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/index.html"}, {"url": "{web}/"}), p=0.5),
            PlanStep(WEB + "fetch", ({"url": "{web}/about.html"}, {"url": "{web}/team.html"}),
                     on_error={"url": "{web}/about.html"}),  # team.html is a 404
        ),
    ),
    Task(
        task_id="web_products_list",
        prompt="What products does the website {web} list, and at what prices?",
        servers=("web_fetch",),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/index.html"},), p=0.4),
            PlanStep(WEB + "fetch", ({"url": "{web}/products.html"}, {"url": "{web}/products.html", "max_length": 2000})),
            PlanStep(WEB + "fetch", ({"url": "{web}/faq.html", "max_length": 2000},), p=0.3),
        ),
    ),
    Task(
        task_id="web_docs_tour",
        prompt="Give me an overview of the documentation on {web}.",
        servers=("web_fetch",),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/index.html"}, {"url": "{web}/"})),
            PlanStep(WEB + "fetch", ({"url": "{web}/docs/getting-started.html"},), p=0.7),
            PlanStep(WEB + "fetch", ({"url": "{web}/docs/api-reference.html"},), p=0.7),
            PlanStep(WEB + "fetch", ({"url": "{web}/docs/index.html"},), p=0.3,
                     on_error={"url": "{web}/docs/getting-started.html"}),  # 404
        ),
    ),
    Task(
        task_id="calc_unit_report",
        prompt="Convert 20, 25 and 30 degrees Celsius to Fahrenheit.",
        servers=("calculator",),
        plan=(
            PlanStep(CALC + "convert_temperature", ({"value": 20, "from_unit": "C", "to_unit": "F"},
                                                    {"value": 20, "from_unit": "c", "to_unit": "f"})),
            PlanStep(CALC + "convert_temperature", ({"value": 25, "from_unit": "C", "to_unit": "F"},), p=0.8),
            PlanStep(CALC + "convert_temperature", ({"value": 30, "from_unit": "C", "to_unit": "F"},), p=0.8),
            PlanStep(CALC + "percentage", ({"part": 30, "whole": 20},), p=0.3),
        ),
    ),
    Task(
        task_id="multi_web_db_prices",
        prompt="Do the prices on {web}/products.html match the database?",
        servers=("web_fetch", "sqlite"),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/products.html"},)),
            PlanStep(DB + "read_query", (
                {"sql": "SELECT name, price FROM products ORDER BY name"},
                {"sql": "SELECT name, price FROM products WHERE category = 'electronics'"},
                {"sql": "SELECT MIN(price) AS lo, MAX(price) AS hi, AVG(price) AS avg FROM products"},
            )),
        ),
    ),
    Task(
        task_id="multi_db_to_csv",
        prompt="Export the product list from the database to documents/products.csv.",
        servers=("sqlite", "filesystem"),
        plan=(
            PlanStep(DB + "read_query", ({"sql": "SELECT id, name, price FROM products ORDER BY id"},
                                         {"sql": "SELECT id, name, category, price, stock FROM products"})),
            PlanStep(FS + "write_file", ({"path": "documents/products.csv", "content": "id,name,price\n1,Widget A,9.99"},
                                         {"path": "documents/export/products.csv", "content": "id,name,category,price,stock"})),
            PlanStep(FS + "list_directory", ({"path": "documents"},), p=0.4),
        ),
    ),
    Task(
        task_id="multi_news_growth",
        prompt="Using the Q3 news on {web}, what share of total revenue came from the East region (57,200)?",
        servers=("web_fetch", "calculator"),
        plan=(
            PlanStep(WEB + "fetch", ({"url": "{web}/news/2026-q3.html"},)),
            PlanStep(CALC + "percentage", ({"part": 57200, "whole": 174400}, {"part": 57.2, "whole": 174.4})),
            PlanStep(CALC + "add_numbers", ({"a": 48000, "b": 57200},), p=0.3),
        ),
    ),
    Task(
        task_id="multi_notes_to_log",
        prompt="Read my notes and record a log entry that the notes were reviewed.",
        servers=("filesystem", "sqlite"),
        plan=(
            PlanStep(FS + "read_file", ({"path": "notes.txt"},)),
            PlanStep(DB + "insert_row", (
                {"table": "logs", "values": {"ts": "2026-10-06T09:00:00Z", "level": "INFO", "message": "notes reviewed"}},
                {"table": "logs", "values": {"ts": "2026-10-06T09:00:00Z", "level": "INFO",
                                              "message": "weekly notes reviewed by assistant"}},
            )),
            PlanStep(DB + "read_query", ({"sql": "SELECT ts, message FROM logs ORDER BY id DESC LIMIT 3"},), p=0.5),
        ),
    ),
    # --------------------- benign servers that use MCP sampling (lab 0.9.1)
    # Their tools ask the client's model to write text (sampling/createMessage), so
    # server-initiated sampling occurs in benign sessions too, in four different tasks.
    Task(
        task_id="assist_summarize_text",
        prompt="Summarize this paragraph about the quarterly sales review for me.",
        servers=("writing_assistant",),
        plan=(
            PlanStep(WRITE + "summarize_text", (
                {"text": "The quarterly review covered sales in three regions. North grew 4 percent, South "
                         "stayed flat and West fell 2 percent after a supplier delay. The team agreed to "
                         "review prices in July.", "max_sentences": 2},
                {"text": "Our team moved the weekly meeting to Thursday. Priya will collect the status "
                         "updates, and the new dashboard goes live next month.", "max_sentences": 1},
                {"text": "The library extends opening hours during exams: weekdays until 10 pm and "
                         "Saturdays until 6 pm. Group rooms must be booked a day in advance.",
                 "max_sentences": 3},
            )),
        ),
    ),
    Task(
        task_id="assist_translate_notes",
        prompt="Read my notes file and translate its first line into another language.",
        servers=("filesystem", "writing_assistant"),
        plan=(
            PlanStep(FS + "read_file", ({"path": "notes.txt"},), p=0.6),
            PlanStep(WRITE + "translate_text", (
                {"text": "Please send the meeting notes before Friday.", "target_language": "French"},
                {"text": "Please send the meeting notes before Friday.", "target_language": "German"},
                {"text": "The quarterly report is ready for review.", "target_language": "Spanish"},
                {"text": "The quarterly report is ready for review.", "target_language": "Hindi"},
            )),
        ),
    ),
    Task(
        task_id="helpdesk_triage_ticket",
        prompt="Sort the incoming customer ticket into the right support queue.",
        servers=("helpdesk",),
        plan=(
            PlanStep(HELP + "classify_ticket", (
                {"ticket": "I was charged twice for order 1042 this month."},
                {"ticket": "My parcel was marked delivered but never arrived."},
                {"ticket": "I cannot reset my password, the email never comes."},
                {"ticket": "Do you have the blue mug in a larger size?"},
            )),
            PlanStep(HELP + "classify_ticket", (
                {"ticket": "Can I change the delivery address of an order that has already shipped?"},
                {"ticket": "Please close my account and delete my saved cards."},
            ), p=0.4),
        ),
    ),
    Task(
        task_id="helpdesk_order_reply",
        prompt="Check how many orders are pending and draft a reply to the customer asking about delays.",
        servers=("sqlite", "helpdesk"),
        plan=(
            PlanStep(DB + "read_query", (
                {"sql": "SELECT status, COUNT(*) AS n FROM orders GROUP BY status"},
                {"sql": "SELECT COUNT(*) AS pending FROM orders WHERE status = 'pending'"},
            )),
            PlanStep(HELP + "draft_reply", (
                {"question": "Why is my order taking longer than usual?", "tone": "friendly"},
                {"question": "Why is my order taking longer than usual?", "tone": "formal"},
                {"question": "When will my pending order ship?", "tone": "friendly"},
            )),
        ),
    ),
]}


def render_task(task: Task, values: dict[str, str]) -> Task:
    """Fill ``{name}`` placeholders (e.g. ``{web}``) in the prompt and plan arguments."""
    def fill(obj: Any) -> Any:
        if isinstance(obj, str):
            for k, v in values.items():
                obj = obj.replace("{" + k + "}", v)
            return obj
        if isinstance(obj, dict):
            return {k: fill(v) for k, v in obj.items()}
        return obj

    plan = tuple(replace(s, choices=tuple(fill(c) for c in s.choices),
                         on_error=fill(s.on_error) if s.on_error else None) for s in task.plan)
    return replace(task, prompt=fill(task.prompt), plan=plan)


def get_task(task_id: str) -> Task:
    try:
        return TASKS[task_id]
    except KeyError:
        raise KeyError(f"Unknown task '{task_id}'. Known: {sorted(TASKS)}") from None
