import os
import sys
from sqlalchemy import create_engine, MetaData, select, text
from sqlalchemy.exc import SQLAlchemyError


def normalize_mysql_uri(uri):
    if uri.startswith('mysql://'):
        return uri.replace('mysql://', 'mysql+pymysql://', 1)
    return uri


def load_uri(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        print(f"Environment variable {name} is not set.")
        sys.exit(1)
    return value


def main():
    sqlite_uri = load_uri('SQLITE_URI', 'sqlite:///app.db')
    mysql_uri = normalize_mysql_uri(load_uri('DATABASE_URI'))

    print('SQLite URI:', sqlite_uri)
    print('MySQL URI:', mysql_uri)

    old_engine = create_engine(sqlite_uri)
    new_engine = create_engine(mysql_uri)

    old_meta = MetaData()
    new_meta = MetaData()

    old_meta.reflect(bind=old_engine)
    new_meta.reflect(bind=new_engine)

    tables = [
        'users',
        'announcements',
        'announcement_images',
        'favorites',
        'tenant_requests',
        'messages',
        'notifications',
        'moderation_actions',
        'backups',
        'saved_searches'
    ]

    try:
        with old_engine.connect() as old_conn, new_engine.begin() as new_conn:
            new_conn.execute(text('SET FOREIGN_KEY_CHECKS=0'))
            for table_name in tables:
                old_table = old_meta.tables.get(table_name)
                new_table = new_meta.tables.get(table_name)

                if old_table is None:
                    print(f"Warning: table '{table_name}' not found in SQLite, skipping.")
                    continue
                if new_table is None:
                    print(f"Error: table '{table_name}' not found in MySQL schema. Run the app once to create tables.")
                    sys.exit(1)

                old_rows = old_conn.execute(select(old_table)).mappings().all()
                if not old_rows:
                    print(f"{table_name}: no rows to copy.")
                    continue

                existing = new_conn.execute(select(new_table).limit(1)).first()
                if existing is not None:
                    print(f"Error: target MySQL table '{table_name}' is not empty. Clear the table before migrating.")
                    sys.exit(1)

                print(f"Copying {len(old_rows)} rows into {table_name}...")
                new_conn.execute(new_table.insert(), [dict(row) for row in old_rows])

            new_conn.execute(text('SET FOREIGN_KEY_CHECKS=1'))

    except SQLAlchemyError as exc:
        print('Ошибка SQLAlchemy:', exc)
        sys.exit(1)

    print('Миграция из SQLite в MySQL завершена.')


if __name__ == '__main__':
    main()
