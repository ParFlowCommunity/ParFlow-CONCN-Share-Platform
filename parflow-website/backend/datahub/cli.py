"""Run from backend: python -m datahub.cli bootstrap|admin|import-catalog."""

import argparse
import getpass
import json
import re
import secrets
from pathlib import Path
import os
from pymysql.constants import CLIENT
from werkzeug.security import generate_password_hash
from .config import BACKEND, ROOT
from .repositories.db import connect, transaction, one, dump
from .common import email, password


def execute_script(conn, path):
    with conn.cursor() as c:
        c.execute(path.read_text(encoding="utf-8"))
        while c.nextset():
            pass


def bootstrap():
    """Create new local application and test databases without reading old SQLite."""
    secret = getpass.getpass("Local MySQL root password: ")
    conn = connect(
        user="root",
        password=secret,
        database="mysql",
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    primary, testing = "concn_datahub", "concn_datahub_test"
    envfile = BACKEND / ".env"
    if envfile.exists():
        raise SystemExit(
            "Refusing to overwrite existing backend/.env. Use the existing configuration."
        )
    app_password = secrets.token_urlsafe(32)
    with conn:
        with conn.cursor() as c:
            for db in (primary, testing):
                if one(
                    c,
                    "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
                    (db,),
                ):
                    raise SystemExit(f"Refusing to overwrite existing database: {db}")
            if one(c, "SELECT User FROM mysql.user WHERE User='concn_app'"):
                raise SystemExit(
                    "concn_app already exists; will not change its password."
                )
            for db in (primary, testing):
                c.execute(
                    f"CREATE DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
                c.execute(f"USE `{db}`")
                execute_script(conn, ROOT / "database/migrations/001_schema.sql")
                execute_script(conn, ROOT / "database/migrations/002_regions.sql")
                execute_script(conn, ROOT / "database/migrations/003_notification_reads.sql")
                execute_script(conn, ROOT / "database/migrations/004_application_usage.sql")
                execute_script(conn, ROOT / "database/seeds/001_defaults.sql")
            c.execute(
                "CREATE USER 'concn_app'@'localhost' IDENTIFIED BY %s", (app_password,)
            )
            c.execute(
                "GRANT SELECT,INSERT,UPDATE,DELETE ON concn_datahub.* TO 'concn_app'@'localhost'"
            )
            c.execute(
                "GRANT ALL PRIVILEGES ON concn_datahub_test.* TO 'concn_app'@'localhost'"
            )
        conn.commit()
    envfile.write_text(
        "MYSQL_HOST=127.0.0.1\nMYSQL_PORT=3306\nMYSQL_DATABASE=concn_datahub\nMYSQL_USER=concn_app\n"
        f"MYSQL_PASSWORD={app_password}\nCONCN_ENV=development\nCONCN_PUBLIC_URL=http://localhost:5173\n"
        "CONCN_REQUIRE_VERIFIED_EMAIL=0\nCONCN_COOKIE_SECURE=0\n",
        encoding="utf-8",
    )
    os.environ.update(
        MYSQL_USER="concn_app", MYSQL_PASSWORD=app_password, MYSQL_DATABASE=primary
    )
    admin_password = "A1" + secrets.token_urlsafe(18)
    with transaction() as c:
        c.execute(
            "INSERT INTO users(username,email,password_hash,role,email_verified_at) VALUES('admin','admin@localhost.test',%s,'admin',UTC_TIMESTAMP(6))",
            (generate_password_hash(admin_password),),
        )
        seed_content(c)
    private = ROOT / ".local"
    private.mkdir(exist_ok=True)
    (private / "admin-credentials.txt").write_text(
        f"Local development only\nLogin: admin@localhost.test\nPassword: {admin_password}\nChange before public deployment.\n",
        encoding="utf-8",
    )
    print(
        "Created concn_datahub + concn_datahub_test, 23 tables each. Runtime user created."
    )
    print(
        "Credentials written to ignored backend/.env and .local/admin-credentials.txt. No root password saved."
    )


def seed_content(c):
    pages = [
        (
            "getting-started",
            "help",
            "从流域到数据包",
            "From basin to data",
            "注册并登录后，选择标准 PFBAS 流域。每个账号可取得两个不同的小流域编码；同一编码可以重复下载。大流域请填写申请表，审核通过后下载。每份申请只包含一个流域，允许多次申请。\n\n首版下载完整数据包，包括已发布的模型输入、掩膜、模拟域文件和元数据。包内说明记录适用版本、单位和引用。五至七级（PFBAS10/12/14）默认属于小流域，管理员可调整规则。",
            "Register and sign in to choose a standard PFBAS basin. Each account may access two distinct small-basin codes. Repeat downloads of the same code do not use another slot. Large basins require an application and approval. Each application covers one basin; further applications are allowed.\n\nDownloads contain the full published input package, masks, domain geometry and metadata. Consult the package documentation for versions, units and citation. Levels 5–7 (PFBAS10/12/14) are small basins by default; administrators can adjust this threshold.",
        ),
        (
            "release-status",
            "notice",
            "数据发布状态",
            "Data release status",
            "平台正在建设中。正式流域目录和数据版本将在完成校验后发布；当前没有已发布数据时，下载功能不会生成示例数据冒充真实结果。",
            "The platform is under development. Basin catalogs and data versions will be published after validation. If no release is available, the service will not substitute synthetic results for real data.",
        ),
    ]
    for slug, kind, zh, en, bz, be in pages:
        c.execute(
            "INSERT INTO content_pages(slug,kind,title_zh,title_en,body_zh,body_en,status,published_at) VALUES(%s,%s,%s,%s,%s,%s,'published',UTC_TIMESTAMP(6))",
            (slug, kind, zh, en, bz, be),
        )


def create_admin():
    address = email(input("Admin email: "))
    name = input("Admin username: ").strip()
    pw = password(getpass.getpass("New admin password: "))
    with transaction() as c:
        c.execute(
            "INSERT INTO users(username,email,password_hash,role,email_verified_at) VALUES(%s,%s,%s,'admin',UTC_TIMESTAMP(6))",
            (name, address, generate_password_hash(pw)),
        )
    print("Admin created.")


def import_catalog(path):
    """Validated JSON catalog. Additive only; no replacement or SQLite import."""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a non-empty list of basins")
    rows.sort(key=lambda r: r["pfbas_level"])
    with transaction() as c:
        for row in rows:
            code, level = row["basin_code"], row["pfbas_level"]
            if (
                not isinstance(code, str)
                or not re.fullmatch(r"[0-9]{14}", code)
                or level not in range(2, 15, 2)
            ):
                raise ValueError("Invalid basin code or level")
            parent = row.get("parent_code")
            if parent:
                p = one(
                    c,
                    "SELECT pfbas_level FROM watersheds WHERE basin_code=%s",
                    (parent,),
                )
                if (
                    not p
                    or p["pfbas_level"] != level - 2
                    or not code.startswith(parent[: level - 2])
                ):
                    raise ValueError("Invalid parent hierarchy")
            c.execute(
                "INSERT INTO watersheds(basin_code,pfbas_level,parent_code,name_zh,name_en,region_zh,region_en,area_km2,center_lng,center_lat,bbox_wgs84,status) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    code,
                    level,
                    parent,
                    row.get("name_zh"),
                    row.get("name_en"),
                    row.get("region_zh"),
                    row.get("region_en"),
                    row.get("area_km2"),
                    row.get("center_lng"),
                    row.get("center_lat"),
                    dump(row.get("bbox_wgs84")),
                    "available",
                ),
            )
    print(f"Imported {len(rows)} basins. No data version published automatically.")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap")
    sub.add_parser("admin")
    sub.add_parser("publish-local")
    p = sub.add_parser("import-catalog")
    p.add_argument("path")
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap()
    elif args.command == "admin":
        create_admin()
    elif args.command == "import-catalog":
        import_catalog(args.path)
    elif args.command == "publish-local":
        from .local_release import publish_local
        publish_local()


if __name__ == "__main__":
    main()
