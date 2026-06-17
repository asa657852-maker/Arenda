# Инструкция по деплою и миграции на MySQL

## Быстрый запуск на Render

Проект готов для деплоя на Render через `render.yaml` и `Procfile`.

1. Зарегистрируйтесь на Render и подключите репозиторий GitHub/GitLab.
2. Render автоматически создаст веб-сервис по `render.yaml`.
3. В Render Dashboard установите секреты:
   - `SECRET_KEY`
   - `ADMIN_PHONE`
   - `ADMIN_PASSWORD`
   - `ADMIN_SMS`
4. После создания сервиса откройте его и запустите.

Приложение использует `DATABASE_URL`, если `DATABASE_URI` не задан, поэтому Render managed MySQL будет подключаться автоматически.

---

1) Установите зависимости в виртуальном окружении:

```powershell
cd c:\Users\Enot\Desktop\arenda_ru
python -m pip install -r requirements.txt
```

2) Подготовьте базу данных MySQL (создайте базу и пользователя):

```sql
CREATE DATABASE arenda_ru CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER 'arenda_user'@'%' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON arenda_ru.* TO 'arenda_user'@'%';
FLUSH PRIVILEGES;
```

3) Установите переменные окружения на хостинге (пример для PowerShell):

```powershell
$env:DATABASE_URI = "mysql+pymysql://arenda_user:strong_password@127.0.0.1:3306/arenda_ru"
$env:ADMIN_PHONE = "99999999999"
$env:ADMIN_SMS = "123456"
$env:ADMIN_PASSWORD = "your_admin_password"
$env:SECRET_KEY = "production-secret-key"
```

4) Запустите приложение один раз, чтобы SQLAlchemy создал таблицы:

```powershell
python app.py
```

5) Если у вас есть локальная SQLite база `app.db` и вы хотите перенести данные, выполните миграцию:

```powershell
$env:SQLITE_URI = "sqlite:///app.db"
$env:DATABASE_URI = "mysql+pymysql://arenda_user:strong_password@127.0.0.1:3306/arenda_ru"
python migrate_sqlite_to_mysql.py
```

Замечания:
- `migrate_sqlite_to_mysql.py` ожидает, что целевая MySQL схема уже создана (шаг 4). Скрипт не выполняет миграцию, если целевые таблицы не пусты.
- Для админ-панели используйте логин по номеру телефона и пароль (если вы задали `ADMIN_PASSWORD`) или по СМС-коду (`ADMIN_SMS`).
- Бэкапы MySQL делаются через `mysqldump` или инструменты хостера, а не через файл `app.db`.

Если хотите, могу добавить systemd/Procfile пример для автозапуска на сервере и Dockerfile для деплоя в контейнере.
